# Bộ demo Sales and Customer Analytics Warehouse

Bản giao ngày 2026-10-19. Đây là **portfolio độc lập với Olist thật**, không phải hệ thống nội bộ Abbott hoặc Concentrix. Bộ này mô tả implementation hiện có; không thay thế design baseline ở docs/visuals.

## Dùng ngay

- [Báo cáo dự án PDF](project-report.pdf): bản gọn 5 trang, dùng ảnh kiến trúc người dùng cung cấp và giữ schema hiện có; tập trung nguồn dữ liệu, quy trình và kết quả.
- [Nội dung báo cáo Markdown](report.md): có thể chỉnh sửa trước khi gửi.
- [PDF sơ đồ](architecture-slides.pdf): 10 hình cho buổi trình bày.
- [Gallery offline](index.html): mở file bằng trình duyệt, chọn Chế độ trình bày; dùng phím trái/phải và Esc.
- [Ghi chú thuyết trình](presentation-notes.md): lộ trình 7 phút và lời giải thích từng hình.
- [ERD Mermaid](warehouse-schema.mmd): nguồn mô hình có từng FK; PNG/SVG hình 10 chỉ rút gọn cột.
- [Phân tích nghiệp vụ](business-analysis.md): số liệu cùng release và giới hạn kết luận.

Ảnh kiến trúc tại `assets/architecture-user.png` được dùng làm ảnh chính của repo và trong báo cáo; bộ 10 hình/PDF sơ đồ kỹ thuật vẫn được giữ. Chú thích dưới ảnh phân biệt 9 file trong archive với 7 feed thực sự nạp và xác định đúng nơi lưu dimensions/facts.

## Danh mục ảnh 4K

| Số | Nội dung | PNG 3840 × 2160 | Vector |
|---|---|---|---|
| 01 | Bài toán và đầu ra của dự án | [PNG](png/01-business-input-output.png) | [SVG](svg/01-business-input-output.svg) |
| 02 | Kiến trúc hệ thống đang chạy | [PNG](png/02-system-architecture.png) | [SVG](svg/02-system-architecture.svg) |
| 03 | Mỗi lớp dữ liệu có một trách nhiệm | [PNG](png/03-data-layers-and-lineage.png) | [SVG](svg/03-data-layers-and-lineage.svg) |
| 04 | Kimball bus matrix và grain | [PNG](png/04-kimball-bus-matrix.png) | [SVG](svg/04-kimball-bus-matrix.svg) |
| 05 | Ba star dùng chung bảy dimensions | [PNG](png/05-dimensional-constellation.png) | [SVG](svg/05-dimensional-constellation.svg) |
| 06 | Workflow thực tế của Airflow | [PNG](png/06-airflow-workflow.png) | [SVG](svg/06-airflow-workflow.svg) |
| 07 | Semantic Layer nằm ở đâu? | [PNG](png/07-semantic-and-serving.png) | [SVG](svg/07-semantic-and-serving.svg) |
| 08 | Không công bố dữ liệu đang xử lý dở | [PNG](png/08-publication-quality-and-recovery.png) | [SVG](svg/08-publication-quality-and-recovery.svg) |
| 09 | Kết quả để trình bày trong buổi demo | [PNG](png/09-dashboards-results-and-evidence.png) | [SVG](svg/09-dashboards-results-and-evidence.svg) |
| 10 | Thiết kế bảng và quan hệ Kimball | [PNG](png/10-warehouse-key-schema.png) | [SVG](svg/10-warehouse-key-schema.svg) |

## Đầu ra thật

Ảnh sáu dashboard nằm ở `screenshots/`. Release `87f01740-0523-5fd4-be0e-eb52acb2842a`, source cut 1; tháng mặc định 2018-07, customer cutoff 2018-08-31. Tỷ lệ và cửa sổ khác nhau không gộp chung thành một KPI.

Business facts: 99.441 orders, 112.650 items, 103.886 payments. 6 dashboard có 60 active objects, không phải 60 chỉ số nghiệp vụ riêng. Metadata lịch sử có thể có nhiều assets hơn. Có 8 saved SQL analyses, 5 MetricFlow exports và 8 core metrics.

`manifest.json` ghi input/output hashes và phạm vi evidence. Current API/browser/health checks được đọc từ lần khởi động demo; retry/recovery/restore sử dụng chứng cứ lịch sử được ghi rõ ngày. Việc xuất kit không chạy lại pipeline hoặc thay release.

## Tái tạo

Từ project root: `python scripts/build_demo_kit.py`. Cần Pillow, Playwright, reportlab, pypdf và Chrome local. Script chỉ đọc các input allowlist; không tải nguồn, không đọc credential, không chạy DDL/SQL/Docker. Xem dependencies trong môi trường làm tài liệu; không thêm chúng vào runtime pipeline.

## Chia sẻ an toàn

Gửi `project-report.pdf` hoặc ZIP demo-kit ở thư mục cha. Kit không chứa raw records, credentials, backups, volumes hay private connection strings. Ảnh dashboard chỉ là aggregate published reports. Giữ attribution Olist CC BY-NC-SA 4.0; giấy phép dữ liệu không suy ra quyền triển khai thương mại cho khách hàng. Không dùng logo Abbott/Concentrix để ngụ ý dự án của họ.
