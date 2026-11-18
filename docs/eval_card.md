# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** `E-swarm-20261118-e1dd` / `e1ddf7d5ff6c`
- **Phiên bản:** eval set v1 · metric_spec.yaml · seeds 11/22/33/44/55
- **Eval set:** v1, 14 item × 5 seed, nguồn lab8_public; nhãn: labels_v1.json
- **Metric & ngưỡng:** approval/secret = 0; refund/pass_rate ≥ 0.95/0.85 và không giảm có ý nghĩa; reply amount ≥ 0.95
- **Kết quả baseline vs PR:** baseline swarm pass_rate 0.9857; fixed 1.0; seeded_regression 0.7143 và gate exit 1
- **Judge:** tone_ok κ=0.757, P=0.857, R=0.800; helpful bị loại vì κ=0.375, recall=0.300
- **Trace case:** link `docs/trace_case.md`, bước sai đầu tiên, regression test
- **Gate owner:** ai xử lý khi gate exit 1
- **Phạm vi pilot:** …
- **Giới hạn / bằng chứng còn thiếu:** MockLLM, 14 item, judge replay; không đo trên người dùng thật
- **Khi nào tăng eval-set version:** …
