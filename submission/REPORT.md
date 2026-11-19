# Báo cáo Day 09 — Hoàng Thu Hương, 2A202603143

> Xoá mọi `TODO(học viên)` và dòng gợi ý. Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước
TODO(học viên): pipeline kết luận **Release / Hold / Rework**? Bao nhiêu ảnh vào, bao nhiêu ảnh ra dataset? Lý do chính (1–3 câu).

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| TODO(học viên) | | | |

TODO(học viên): vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy? Với ngân sách 80 ảnh, người xem được bao nhiêu lỗi ngữ nghĩa?

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | TODO(học viên) | | |
| `second_opinion.conf` | 0.25 | TODO(học viên) | | |

TODO(học viên): **một chỗ calibration có thể đánh lừa bạn**, kèm bằng chứng từ dữ liệu của bạn (vd. mở xem vài cặp ảnh bị cho là trùng; số ảnh bị loại ở bước 1 có hợp lý không?).

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
TODO(học viên): (a) chứng minh gate chặn đúng: chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên ảnh thiếu file nhãn còn nguyên), chỉ ra kết luận **Rework**, mã thoát 20 và việc **không xuất** dataset. (Đừng sửa tay `work/run/ds`: pipeline dựng lại thư mục này từ raw mỗi lần chạy.) (b) ≥ 2 điểm mù có bằng chứng (box lỏng nhẹ, nhầm lớp mà model lớn cũng nhầm, ảnh trùng biến đổi mạnh…).

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa train: ghi "chưa chạy" và lý do, rồi bỏ qua phần còn lại của mục này. Nếu đã train: dán bảng từ `submission/results/comparison.md` (model, epoch, seed, số ảnh train mỗi biến thể).

TODO(học viên): chênh mAP50 (clean − raw) so với **độ lệch chuẩn giữa các seed**; kết luận **trung thực** (nằm trong nhiễu thì nói là chưa kết luận được); ≥ 2 giả thuyết giải thích (ảnh trùng/rò rỉ test trong `raw`, nhãn máy còn lại trong `clean`, test chỉ 100 ảnh…) và cách kiểm.

## 6. Quyết định và ghi chú AI

### (a) Quyết định cuối
TODO(học viên): quyết định cuối; nếu Hold/Rework cần làm gì để thành Release?

### (b) Ghi chú dùng AI

**Có dùng AI** (Claude Code) viết `pipeline/checks/label_format.py`.

- **Prompt chính** label_format.py: spec là docstring của `label_format.py` (định dạng vào: nhãn YOLO txt, 5 cột `id cx cy w h` tỉ lệ 0–1; bảng 7 mã lỗi) + 3 test mẫu (`test_bad_format_and_line_numbers`, `test_overflow_vs_tolerance`, `test_duplicate_box_reports_later_line`) + ràng buộc: dùng sẵn `ds.read_label_lines` / `parse_yolo_line` / `iou_xywh`, trả `list[Issue]`, ngưỡng đọc từ `cfg["label_format"]` không viết cứng, dòng hỏng thì `continue`, chỉ đọc không sửa file.

- **Cách kiểm:** (1) đọc lướt — không xoá/ghi file, không `except: pass`, ngưỡng lấy từ `cfg`; (2) `pytest tests/test_label_format.py -q` → 14/14 xanh; (3) đọc kỹ các logic chính: try/except khi parse, check ID class in range, check empty box raise if w or h <=0, check overflow: calculate normalized x, y and define overflow -> raise if overflow > lf["overflow_tol"], check duplicate box: create a dictionary for created box (history_by_class), loop each box through iou_xywh() and compare with dup_box threshold, warn tiny box: base on img_size -> find min(x,y) and compare with threshold. (4) chạy full suite: 55→41 failed (đúng +14 test của module này).
- **1 lần AI sai:** chưa gặp ở module này

**Prompt `gate.py`:**
- (1) Implement hàm `decide(issues, image_stems, cfg, reviewed=frozenset())`.
- (2) Quy tắc kiểm: có ≥ 1 `ERROR` → `Rework` (kể cả ảnh đã duyệt). Nếu không có `ERROR`, tính tỉ lệ = số ảnh khác nhau có `WARN` / tổng số ảnh; chỉ đếm `WARN` của ảnh trong `image_stems` và chưa có trong `reviewed`; tỉ lệ ≥ `cfg["gate"]["warn_ratio_hold"]` → `Hold`, còn lại → `Release`.
- (3) Output: trả dict `decision, n_errors, n_warn_images, n_images, warn_ratio`, `reasons`.
- (4) Giới hạn: không sửa file, không đổi ngưỡng; code ngắn, dễ đọc.

**Cách kiểm:** đọc lướt (không ghi/xoá file, không `except: pass`, ngưỡng lấy từ `cfg`), chạy `pytest tests/test_label_format.py -q` → 14/14 và `pytest tests/test_gate.py -q` → 1


*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
