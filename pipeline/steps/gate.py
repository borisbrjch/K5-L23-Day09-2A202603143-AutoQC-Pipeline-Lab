"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    image_set = set(image_stems)
    reviewed_set = set(reviewed)

    n_images = len(image_stems)
    n_errors = sum(1 for i in issues if i.severity == ERROR)

    # Đếm số ảnh có ít nhất 1 cảnh báo (chỉ tính ảnh trong dataset, chưa duyệt)
    warn_images = set()
    for i in issues:
        if i.severity != WARN:
            continue
        if i.image not in image_set:
            continue
        if i.image in reviewed_set:
            continue
        warn_images.add(i.image)

    n_warn_images = len(warn_images)
    warn_ratio = 0 if n_images == 0 else round(n_warn_images / n_images, 4)
    threshold = cfg["gate"]["warn_ratio_hold"]

    reasons = []
    if n_errors >= 1:
        decision = "Rework"
        reasons.append(f"Còn {n_errors} lỗi bắt buộc (ERROR), cần sửa trước khi phát hành.")
    elif warn_ratio >= threshold:
        decision = "Hold"
        reasons.append(
            f"Có {n_warn_images}/{n_images} ảnh còn cảnh báo (tỉ lệ {warn_ratio}, "
            f"ngưỡng {threshold}), cần người duyệt thêm."
        )
    else:
        decision = "Release"
        reasons.append(
            f"Không có lỗi bắt buộc; {n_warn_images}/{n_images} ảnh còn cảnh báo "
            f"(tỉ lệ {warn_ratio}, dưới ngưỡng {threshold})."
        )

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }
