# Báo cáo từ Warehouse đã công bố

Các CSV này được xuất từ validated MetricFlow exports trong PostgreSQL, không phải dữ liệu sinh ngẫu nhiên. `release_id` cho biết bản Warehouse mà mỗi dòng thuộc về. [Manifest](../../docs/evidence/runtime/manifest.json) ghi checksum, số dòng, pipeline run và thời điểm đóng gói.

| Báo cáo | Grain, ngoài release_id | Số dòng của lần chụp hiện tại |
|---|---|---:|
| [sales_monthly.csv](sales_monthly.csv) | Tháng mua hàng | 25 |
| [sales_daily.csv](sales_daily.csv) | Ngày mua hàng | 634 |
| [product_monthly.csv](product_monthly.csv) | Tháng × category | 1.283 |
| [seller_monthly.csv](seller_monthly.csv) | Tháng × seller | 16.441 |
| [buyer_state_monthly.csv](buyer_state_monthly.csv) | Tháng × bang của người mua | 565 |

Delivered merchandise value là tổng giá hàng của đơn có trạng thái delivered trong snapshot đã chấp nhận, chưa gồm freight. BRL là quy ước demo. AOV = delivered merchandise value / delivered orders, NULL khi mẫu số bằng 0. Cancellation rate dùng canceled / total orders, lưu dạng tỷ lệ 0–1. Không cộng distinct customers giữa các tháng; không lấy trung bình AOV giữa các nhóm. Product/seller reports không có order AOV vì chưa có định nghĩa attribution phù hợp grain.

Các số liệu thể hiện snapshot nguồn, không tái dựng trạng thái lịch sử tại ngày giao dịch. Nguồn Olist có khoảng thời gian quan sát không đầy đủ ở đầu/cuối; không suy diễn xu hướng doanh nghiệp hiện tại từ các phần kỳ thiếu dữ liệu.

Attribution: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), Olist, CC BY-NC-SA 4.0 theo metadata nhà công bố. Đây là kết quả tổng hợp/chuyển đổi của dự án portfolio độc lập; giữ điều kiện attribution, noncommercial và share-alike khi chia sẻ dữ liệu phái sinh. Quyền sử dụng dữ liệu tách biệt với code; dữ liệu không thuộc Abbott/Concentrix.

Tái tạo trên máy đang chạy hệ thống: `make verify-runtime verify-bi verify-browser package-evidence`.
