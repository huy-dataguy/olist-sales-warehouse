# Bộ hình kiến trúc và trình bày dự án

**Dùng cho buổi demo hiện tại:** [bộ 10 sơ đồ implementation và báo cáo dự án](../../output/demo-kit/README.md), dùng Apache Superset và bằng chứng chạy thật. Bộ 9 hình dưới đây được giữ nguyên như baseline thiết kế lịch sử.

9 hình, khổ 16:9. Nội dung tiếng Việt, tên bảng/công nghệ giữ nguyên để đối chiếu specs. Baseline: thiết kế 2.0.0 ngày 2026-10-15.

Đây là bộ sơ đồ của **baseline thiết kế**. Sau đó hệ thống đã được triển khai và kiểm thử runtime; xem [ảnh dashboard thật](../evidence/runtime/screenshots/), [manifest kết quả](../evidence/runtime/manifest.json) và [coverage hiện tại](../implementation-progress.md). Nhãn “runtime chưa nghiệm thu” trên hình 09 ghi lại thời điểm thiết kế, không phải trạng thái mới nhất của hệ thống.

## Mở và sử dụng

- [Mở toàn bộ hình, có chế độ trình bày](index.html): mở bằng trình duyệt, không cần server hay Internet.
- [PDF 9 trang](../../output/pdf/project-architecture.pdf): dùng khi trình bày, gửi kèm hồ sơ hoặc in.
- [Ghi chú thuyết trình](presentation-notes.md): lộ trình 5 phút và phần giải thích kỹ thuật.
- `png/`: ảnh 3840 × 2160 để chèn vào slide.
- `svg/`: bản vector, có thể phóng to và chỉnh sửa bằng công cụ hỗ trợ SVG.

Trong trang xem, chọn **Chế độ trình bày**. Phím trái/phải hoặc Page Up/Page Down chuyển hình; Esc trở về trang có ghi chú. Không có tracking, CDN hay kết nối dữ liệu bên ngoài.

## Danh mục hình

| # | Nội dung | PNG | Vector |
|---|---|---|---|
| 01 | Mục tiêu, người dùng, input, output, ngoài phạm vi | [PNG](png/01-objectives-input-output.png) | [SVG](svg/01-objectives-input-output.svg) |
| 02 | Dữ liệu nguồn, quy mô, baseline, vấn đề thật | [PNG](png/02-source-data-and-baseline.png) | [SVG](svg/02-source-data-and-baseline.svg) |
| 03 | Kiến trúc từ nguồn đến BI, vai trò từng thành phần | [PNG](png/03-system-architecture.png) | [SVG](svg/03-system-architecture.svg) |
| 04 | Kimball bus matrix và grain ba business process | [PNG](png/04-kimball-bus-matrix.png) | [SVG](svg/04-kimball-bus-matrix.svg) |
| 05 | Constellation: facts và conformed dimensions | [PNG](png/05-dimensional-constellation.png) | [SVG](svg/05-dimensional-constellation.svg) |
| 06 | Pipeline logic Airflow, checkpoint, retry và lỗi | [PNG](png/06-airflow-pipeline-and-recovery.png) | [SVG](svg/06-airflow-pipeline-and-recovery.svg) |
| 07 | Semantic Layer, drill-across, đúng metric grain | [PNG](png/07-semantic-layer-and-correct-metrics.png) | [SVG](svg/07-semantic-layer-and-correct-metrics.svg) |
| 08 | Candidate/published release và nhất quán dashboard | [PNG](png/08-release-publication-and-isolation.png) | [SVG](svg/08-release-publication-and-isolation.svg) |
| 09 | Bằng chứng hiện có, runtime gates, mục tiêu vận hành | [PNG](png/09-evidence-operations-and-success.png) | [SVG](svg/09-evidence-operations-and-success.svg) |

## Cách đọc đúng

- Hình 03 và 06 đi hàng trên từ trái sang phải, rồi hàng dưới từ phải sang trái; đọc theo số thứ tự.
- Hình 04: `X` nghĩa dimension áp dụng cho process; dấu `-` là không áp dụng. Purchase date của payment là ngữ cảnh đơn, không phải payment event time.
- Hình 05 là sơ đồ logic rút gọn, không phải toàn bộ physical ERD. Bốn dimension chung được lặp lại để thấy rõ từng star; không tạo bản sao dimension theo fact. Source namespace luôn nằm trong business grain dù một số nhãn trên hình được rút gọn.
- `fct_orders` là accumulating snapshot theo trạng thái đã chấp nhận, không tái dựng lịch sử trạng thái tại ngày mua.
- Hình 07 dùng ví dụ tổng hợp độc lập: không gán con số 150/300 cho nguồn Olist.
- Hình 08 dùng R0/R1 như tên minh họa, không phải release runtime đã tồn tại. Có nhiều bản retained từng published, nhưng pointer chỉ chọn một bản hiện hành.
- Các thời gian, latency và RPO/RTO trên hình 09 là **mục tiêu thiết kế**. Số đo thực tế sau triển khai được ghi riêng trong runtime reports; không thay thế mục tiêu bằng kết quả một lần đo. Backup cùng host không có bảo đảm mất host.
- 451.535 là tổng dòng của 7 feed; không phải số đơn và cũng không phải số cuộc gọi. 137 checks và 5 semantic checks là offline/design evidence.

## Nguồn nội dung

Source of truth vẫn là [spec index](../../specs/spec-package/00-index.md), [Kimball design](../../specs/spec-package/03-data/kimball-design.md), [kiến trúc](../../specs/spec-package/02-architecture/production-local.md), [semantic contract](../../specs/spec-package/03-data/semantic-and-metrics.md) và [operating model](../../specs/spec-package/08-operations/operating-model.md).

[manifest.json](manifest.json) liên kết từng hình với các tài liệu nguồn và ghi chú. Dataset: [Olist do nhà công bố cung cấp](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), CC BY-NC-SA 4.0 theo metadata đã lưu. Quyền sử dụng dữ liệu tách biệt với code và bộ hình; không suy ra quyền dùng thương mại cho khách hàng.

Không dùng logo doanh nghiệp, không khẳng định dataset là dược phẩm hoặc kiến trúc nội bộ Abbott/Concentrix. MinIO local đã build/start/PUT/GET thành công; upstream không được bảo trì vẫn là giới hạn được ghi trong [runtime coverage](../implementation-progress.md).

## Tái tạo hình

Đầu vào nội dung và layout: [scripts/build_project_visuals.py](../../scripts/build_project_visuals.py). Các SVG/PNG/HTML/PDF là output sinh từ script; sửa script trước rồi xuất lại để tránh lệch bản.

Tooling riêng cho tài liệu, không thêm vào dependency của pipeline:

```bash
# Nếu máy đã có Pillow và Playwright:
python3 scripts/build_project_visuals.py

# Môi trường Python cô lập, phiên bản tooling cố định:
uv run --no-project --python 3.12 --with Pillow==12.3.0 --with playwright==1.63.0 python scripts/build_project_visuals.py
```

Cần Chrome/Chromium cài sẵn, font DejaVu Sans và Poppler `pdfinfo`. Script dùng browser local để render SVG; chặn HTTP/HTTPS, không tự tải browser và không chạy DDL/Docker/pipeline. PDF giữ vector và text; PNG mặc định xuất ở 4K.

## Kiểm chứng hình

[visual-verification.json](visual-verification.json) ghi bounds của các nhãn, kích thước PNG, điều khiển trình bày và kiểm tra trang xem ở chiều rộng 390px. `contact-sheet.png` là tờ duyệt nhanh, không thay thế ảnh full-size khi trình bày.

PDF được kiểm tra đủ 9 trang, tỷ lệ 16:9, render lại bằng Poppler và duyệt bố cục. Đây là kiểm chứng tài liệu, không phải kiểm chứng hệ thống DE đang vận hành.
