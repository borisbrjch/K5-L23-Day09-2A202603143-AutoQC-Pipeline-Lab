"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    issues = []
    lf = cfg["label_format"] # config threshold

    for label_path in ds.label_files():
        stem = label_path.stem
        lines = ds.read_label_lines(stem)
        if not lines:
            continue

        history_by_class = {}
        img_size = ds.image_size(stem)

        for lineno, text in lines:
            # Parse 
            try:
                cls, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem, f"Không parse được: {e}", line=lineno))
                continue

            # Check class ID
            if not (0 <= cls < len(ds.classes)):
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem, f"ID {cls} không hợp lệ", line=lineno))
                continue

            # Check empty box
            if w <= 0 or h <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem, f"Box rỗng w={w} h={h}", line=lineno))
                continue

            # Check box overflow
            left, right = cx - w/2, cx + w/2
            top, bottom = cy - h/2, cy + h/2
            overflow = max(0, -left, right - 1, -top, bottom - 1)

            if overflow > lf["overflow_tol"]:
                issues.append(Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                                  f"Tràn {overflow:.4f}", line=lineno, extra={"overflow": overflow}))

            # Check Box Duplicate
            box = (cx, cy, w, h)
            if cls in history_by_class:
                for prev_box in history_by_class[cls]:
                    if iou_xywh(box, prev_box) > lf["dup_box_iou"]:
                        issues.append(Issue("label_format", ERROR, "DUP_BOX", stem, "Box trùng", line=lineno))
                        break

            history_by_class.setdefault(cls, []).append(box)

            # Warn tiny box 
            if img_size:
                W, H = img_size
                short_px = min(w * W, h * H)
                if short_px < lf["min_box_px"]:
                    issues.append(Issue("label_format", WARN, "BOX_TINY", stem,
                                      f"Nhỏ {short_px:.1f}px", line=lineno))

            if w * h > lf["max_box_frac"]:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem,
                                  f"Lớn {w*h:.1%}", line=lineno))

    return issues
