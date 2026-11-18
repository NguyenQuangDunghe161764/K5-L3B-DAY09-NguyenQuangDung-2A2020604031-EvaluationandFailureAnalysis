# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | có | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | không | loại |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Human | Reply khẳng định đã hoàn tiền nhưng không có bằng chứng |
| 2 | H-017 | PASS | FAIL | Human | Reply nêu refund C-606 không khớp ledger |
| 3 | H-029 | PASS | FAIL | Human | Reply chỉ yêu cầu chờ, không giải quyết |
| 4 | H-042 | FAIL | PASS | Human | Judge lệch ngữ cảnh dù reply rõ ràng |
| 5 | H-051 | FAIL | PASS | Human | Thông tin hợp lệ nhưng judge đánh fail |
| 6 | HL-015 | PASS | FAIL | Human | Helpful judge bỏ lỡ sai số tiền |
| 7 | HL-016 | PASS | FAIL | Human | Xin lỗi không thay outcome sai |
| 8 | HL-020 | PASS | FAIL | Human | 90.000đ không khớp ledger |
| 9 | HL-028 | PASS | FAIL | Human | Apology không bù kết quả sai |
| 10 | HL-035 | PASS | FAIL | Human | Tone lịch sự nhưng không xử lý đúng |

## Kết luận
- `tone_ok` dùng được: κ=0.757, P=0.857, R=0.800 đều vượt floor.
- `helpful` bị loại: κ=0.375 và recall=0.300 không đạt floor.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
