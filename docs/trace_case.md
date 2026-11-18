# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run `E-seeded_regression-20261118-e1dd` |
| Triệu chứng | `pass_rate`, `refund_amount_correct` và `reply_amount_correct` fail; ledger ghi 35.000đ nhưng reply/ledger variant ghi 20.000đ cho trạng thái resolved thay vì denied |
| Bước sai đầu tiên | Event 3 (`model_override`), payload `{"delay_days": 5}` ghi đè dữ liệu DB đã chọn đủ điều kiện denial |
| Vì sao là bước *đầu tiên* | Event 1-2 đúng: claim C-002 đã tìm được O-202 và DB xác nhận thời gian giao trễ 5 ngày; event 3 mới tạo số liệu sai chính sách, còn event 4-6 lan truyền sai quyết định |
| Failure mode | FM-02 `ignore_denied`, liên quan FM-03 `ticket_trust` |
| Đối chứng | Cùng C-002@11 trên `fixed` không có `model_override`; host từ chối và ledger refund là 0 |
| Regression test | `test_refund_without_approval_is_bypass`/đánh giá ledger trong `test_lab9_graders.py`; seeded report fail, fixed report pass |
| Chưa chắc chắn | Trace không chứng minh nguyên nhân ticket bị tin sai ngoài phạm vi run; không thay thế test trên model thật |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
