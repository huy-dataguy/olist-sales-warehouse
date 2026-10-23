# Bộ phân tích có thể tái lập

[Đọc báo cáo tiếng Việt](business-analysis.md) hoặc mở [notebook](analysis.ipynb). Các bảng CSV cùng thư mục là kết quả truy vấn thật từ một published release, không phải dữ liệu minh họa. `results.json` ghi release, cutoff, query SHA và kết quả đối soát.

| File | Nội dung |
|---|---|
| monthly.csv | KPI tháng, so với đúng tháng trước và cùng tháng năm trước |
| categories.csv | Category contribution/cumulative share trong tháng đã chọn |
| sellers.csv | Seller contribution/concentration trong tháng đã chọn |
| customer_segments.csv | Tần suất mua delivered, observed value và recency |
| cohorts.csv | Cohort size, distinct activity và observed retention; giữ M0 và cohort nhỏ 2016 để audit |
| delivery.csv | Số quan sát hợp lệ, đúng hẹn và thời gian giao theo buyer state |
| payments.csv | Phương thức, records, đơn có dùng phương thức và recorded amount |
| quality.csv | Cảnh báo nguồn của producer run cụ thể |

SQL gốc ở `analysis/sql/`; bản đã bind cùng release có trong Superset SQL → Saved queries. Cutoff khách hàng là 31/08/2018, không dùng ngày máy hiện tại. Chart cohort chỉ hiển thị 2017 trở đi, tháng tuổi 1–6 để dễ so sánh; CSV giữ dữ liệu đầy đủ.

Chạy lại từ root repository: `make analyze`. Kiểm notebook: `uv run --no-project --with nbclient --with ipykernel python scripts/execute_analysis_notebook.py`. Notebook đọc CSV local, không cần credential Warehouse; tạo lại bằng make analyze sẽ sinh bản chưa execute để chạy mới.

Nguồn Olist v2, [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), CC BY-NC-SA 4.0 theo metadata nhà công bố. Giữ attribution/noncommercial/share-alike khi chia sẻ dữ liệu phái sinh. Đây là phân tích portfolio độc lập, không phải dữ liệu Abbott/Concentrix.
