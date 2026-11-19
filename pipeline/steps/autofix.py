"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def clip_line(text):
    """Cắt box về trong [0,1]. Trả về dòng mới, hoặc None nếu box không còn diện tích."""
    cls, cx, cy, w, h = parse_yolo_line(text)
    left = max(0.0, cx - w / 2)
    right = min(1.0, cx + w / 2)
    top = max(0.0, cy - h / 2)
    bottom = min(1.0, cy + h / 2)
    new_w = right - left
    new_h = bottom - top
    if new_w <= 0 or new_h <= 0:
        return None
    new_cx = (left + right) / 2
    new_cy = (top + bottom) / 2
    return f"{cls} {new_cx:.6f} {new_cy:.6f} {new_w:.6f} {new_h:.6f}"


def fix(ds, issues, cfg):
    fixes = []
    errors = [i for i in issues if i.severity == ERROR]

    # 1) Lỗi cấp ảnh / dataset
    removed = set()
    renamed = False
    for i in errors:
        if i.code in REMOVE_CODES:
            if i.image in removed:
                continue
            img = ds.image_path(i.image)
            if img is not None:
                img.unlink()
            label = ds.label_path(i.image)
            if label.exists():
                label.unlink()
            removed.add(i.image)
            fixes.append(dict(image=i.image, line=None, action="remove_image",
                              before=i.code, after="đã xoá ảnh + nhãn"))

        elif i.code == "MISSING_LABEL_FILE":
            # Không tạo file nhãn: máy không bịa nhãn, chuyển cho người gán
            fixes.append(dict(image=i.image, line=None, action="needs_label",
                              before="(không có file)", after="chuyển người gán"))

        elif i.code == "BAD_CLASS_NAME" and not renamed:
            data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
            before = data.get("names")
            data["names"] = list(cfg["classes"])
            ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            renamed = True
            fixes.append(dict(image="data.yaml", line=None, action="rename_classes",
                              before=str(before), after=str(cfg["classes"])))

    # 2) Gom lỗi dòng theo file: {stem: {số_dòng: {các mã lỗi}}}
    by_file = defaultdict(lambda: defaultdict(set))
    for i in errors:
        if i.line is not None and (i.code in DROP_CODES or i.code == "BOX_OUT_OF_IMAGE"):
            by_file[i.image][i.line].add(i.code)

    # 3) Sửa từng file, ghi lại MỘT lần
    for stem, line_codes in by_file.items():
        if stem in removed:
            continue
        path = ds.label_path(stem)
        if not path.exists():
            continue

        old_lines = path.read_text(encoding="utf-8").splitlines()  # giữ cả dòng trống
        new_lines = []
        for lineno, text in enumerate(old_lines, 1):
            codes = line_codes.get(lineno)
            if not codes:
                new_lines.append(text)
                continue

            if codes & DROP_CODES:
                fixes.append(dict(image=stem, line=lineno, action="drop_line", before=text, after=""))
                continue

            # Chỉ còn BOX_OUT_OF_IMAGE
            clipped = clip_line(text)
            if clipped is None:
                fixes.append(dict(image=stem, line=lineno, action="drop_line", before=text, after=""))
            else:
                new_lines.append(clipped)
                fixes.append(dict(image=stem, line=lineno, action="clip_box", before=text, after=clipped))

        path.write_text("".join(l + "\n" for l in new_lines), encoding="utf-8")

    return fixes
