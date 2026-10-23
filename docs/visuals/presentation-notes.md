# Ghi chú thuyết trình

## Mở đầu, khoảng 20 giây

“Tôi thiết kế Sales & Customer Analytics Warehouse để chứng minh khả năng xây một nguồn phân tích đáng tin cậy từ dữ liệu thật. Dự án tập trung vào Kimball modeling, dbt, Semantic Layer và vận hành pipeline. Đây là portfolio độc lập, không phải mô tả kiến trúc nội bộ Abbott hay Concentrix.”

Hiện tại nói **“đã thiết kế và kiểm chứng offline”**, không nói “đã vận hành production”. Chỉ đổi cách diễn đạt khi có runtime evidence tương ứng.

## Lộ trình khoảng 5 phút

| Hình | Thời gian gợi ý | Thông điệp chính |
|---|---|---|
| 01 | 35 giây | Bài toán và output: dữ liệu, KPI, BI và khả năng truy vết/khôi phục. |
| 02 | 30 giây | Có nguồn thật và baseline độc lập; không phóng đại quy mô. |
| 03 | 45 giây | Vai trò Airflow, dbt, Warehouse, MetricFlow và BI không chồng lấn. |
| 04 | 30 giây | Business process và grain là nền của thiết kế Kimball. |
| 05 | 25 giây | Conformed dimensions, không join atomic facts. |
| 06 | 35 giây | Tính đúng khi retry, checkpoint và lỗi. |
| 07 | 35 giây | Metric đúng grain, ratio/distinct không cộng ngây thơ. |
| 08 | 35 giây | Không publish kết quả dở; mọi consumer cùng release. |
| 09 | 30 giây | Bằng chứng hiện tại và gate để nghiệm thu thật. |

Tổng khoảng 5 phút. Nếu chỉ có 2 phút, dùng 01 → 03 → 04 → 09. Nếu hội đồng hỏi sâu về tính đúng, dùng 05 → 07 → 08. Không cần ép người xem đọc toàn bộ nhãn trên tất cả hình.

## 01. Mục tiêu và đầu vào/đầu ra

- Bắt đầu bằng nhu cầu: business cần số đơn, giá trị hàng và khách hàng đáng tin cậy; operator cần biết pipeline sai ở đâu và khôi phục thế nào.
- Input là dữ liệu Olist, không phải bộ khách hàng hoặc sản phẩm Abbott. Output runtime được đặc tả: 7 dims, 3 facts, 8 KPI, 5 exports, 3 dashboards.
- Telesales bị loại vì không có dữ liệu phù hợp, không phải vì pipeline né nghiệp vụ khó.

## 02. Nguồn dữ liệu và baseline

- 7 feed có tổng 451.535 dòng nhưng chỉ 99.441 đơn. 99.441 customer references ánh xạ thành 96.096 durable customer identities.
- 13.221.498,11 là giá trị hàng của đơn delivered, loại freight; không gọi là net revenue hay doanh thu nền tảng. BRL là quy ước demo, không phải field currency trong nguồn.
- Những đơn thiếu child records, thiếu timestamp hoặc lệch payment là source warnings được ghi rõ. Transformation phải bảo toàn và giải thích, không âm thầm xóa cho khớp.
- Nguồn Olist là một nhà công bố; không tự gọi 7 file thành 7 hệ thống nguồn độc lập.

## 03. Kiến trúc tổng thể

- Airflow quản lý task dependencies/retries/state; dbt quản lý graph và transformation SQL.
- MinIO giữ source-native raw để replay; PostgreSQL chứa accepted versions, working models, Warehouse releases và reporting exports ở các boundary riêng.
- BI không đọc working models; MetricFlow chạy tại một release cố định rồi ghi exports. Không giả định Metabase có native local MetricFlow connector.
- Một host phù hợp workload local; không tự thêm MPP/Kafka/Spark khi chưa có nhu cầu.

## 04. Bus matrix

- Ba process: sales lines, payment records và order fulfillment. Mỗi process có grain riêng.
- Nguồn không có quantity field; item ordinal không phải quantity. Installments cũng không được nhân vào payment amount.
- Payment chỉ có purchase-date context. Không tự gán product/seller vào payment khi chưa có allocation contract.

## 05. Constellation

- Các star dùng chung định nghĩa/key registry của customer, date, buyer geography và status. Hai dimension riêng của items là product và seller; payment có method.
- Integer SK giữ ổn định qua replay/rebuild. Địa chỉ theo đơn tách khỏi durable customer identity để không viết lại lịch sử địa lý.
- Unknown/inferred member được quản lý có chủ đích. Type 2 chỉ có ý nghĩa khi biết effectivity; Olist snapshot không chứng minh được lịch sử đó.
- Physical FK phải cùng release; sơ đồ đã rút gọn các audit columns và release keys để dễ trình bày.

## 06. Pipeline và phục hồi

- Một receipt là một lần nhận; business batch/source version là identity khác. Retry có thể tăng audit attempts nhưng không tăng business rows.
- Một cut nguồn được cố định cho mọi model. Checkpoint của model chỉ tiến khi materialization tương ứng thành công.
- Transient failure có thể retry. Schema conflict phải quarantine và chẩn đoán, không retry vô hạn. Notification thành công không được biến failed pipeline thành success.
- Đây là luồng logic; task names/materialization cụ thể còn phải được triển khai và kiểm chứng.

## 07. Semantic Layer

- Tính item amount và order count độc lập, aggregate theo cùng purchase period/buyer geography, rồi drill-across để tính AOV.
- Ví dụ fixture: 2 items tổng 150, 2 payments. Join atomic rows làm tổng thành 300; phép tính này chỉ để minh họa fanout.
- AOV phải tính từ tổng tử số/mẫu số, không average các AOV ngày. Distinct khách phải query đúng kỳ, không cộng distinct các nhóm con.
- Chỉ group metric theo dimension được hợp đồng cho phép. Không bịa AOV product-level để thêm một chart.

## 08. Release và publication

- R0/R1 là tên minh họa. R1 có snapshot Warehouse và exports riêng, chưa visible cho BI trong lúc kiểm tra; R0 tiếp tục phục vụ.
- Owner/fence phải hợp lệ khi đổi pointer. Missing binding hoặc stale worker phải fail closed.
- Mọi card cùng pin release để không đọc nửa cũ nửa mới. Các link cũ còn hoạt động trong thời gian release được giữ.
- Atomic boundary ở PostgreSQL, không trải qua Metabase API. Lỗi bàn giao link là delivery lag, không tự khẳng định DB chưa commit.

## 09. Kiểm chứng và vận hành

- Đã có source archive, profile, 137 checks thiết kế và 5 semantic checks offline. Chúng không chứng minh hệ thống Docker hay database đang chạy.
- 22 scenario là đặc tả cần thực thi: replay, correction, failure, concurrency, permission, capacity, restore.
- Các con số latency, batch duration, RPO/RTO là target. Một host không có HA; backup cùng host không chống mất host.
- Sau triển khai, demo có sức thuyết phục nhất gồm: output thật → replay không đổi sai → lỗi bị chặn → recovery và evidence.

## Kết thúc

“Điểm tôi muốn chứng minh không phải số công cụ đã dùng, mà là khả năng thiết kế grain và metric đúng, giữ dữ liệu truy vết được, và bảo vệ đầu ra khi pipeline gặp lỗi. Phần triển khai sẽ được nghiệm thu bằng dữ liệu và kết quả chạy thật theo các gate đã đặc tả.”
