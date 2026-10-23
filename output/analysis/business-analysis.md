# Phân tích Sales & Customer — Olist

Release `87f01740-0523-5fd4-be0e-eb52acb2842a` · source cut 1 · tháng phân tích **2018-07** · cutoff khách hàng **31/08/2018**.

## 1. Bán hàng đang ở mức nào?

Tháng được chọn có **867,953.46 BRL** giá trị hàng thuộc đơn delivered, **6,159** đơn và **6,100** khách hàng phân biệt. AOV **140.92 BRL/đơn**; cancellation rate **0.65%**.

Giá trị hàng thay đổi **1.39%** so với đúng tháng trước và **80.22%** so với cùng tháng năm trước. Đây là mô tả snapshot, chưa kiểm soát độ đầy đủ của nguồn hoặc thay đổi cơ cấu; không suy ra quan hệ nhân quả. Kỳ cuối 2018-08 cần thận trọng về right-censoring nên không được dùng mặc định để kết luận doanh nghiệp suy giảm.

## 2. Nên chú ý danh mục/người bán nào?

Category đứng đầu là **health_beauty**, chiếm **11.93%** giá trị delivered của tháng. Top 10 sellers chiếm **14.15%**. Có thể dùng danh sách này để chọn đối tượng kiểm tra vận hành/nguồn cung trước; dataset không có cost, margin hoặc inventory để khuyến nghị tăng lợi nhuận hay bổ sung tồn kho.

| category | delivered_merchandise_value | delivered_item_rows |
| --- | --- | --- |
| health_beauty | 103,524.22 | 770 |
| watches_gifts | 95,164.79 | 521 |
| housewares | 62,583.30 | 564 |
| bed_bath_table | 54,405.23 | 617 |
| sports_leisure | 54,015.89 | 460 |

## 3. Khách hàng có mua lại không?

Có **2,801/93,358** khách từng có ít nhất hai đơn delivered, tương đương **3.00%**. Nhóm này đóng góp **5.51%** merchandise value quan sát. Tỷ lệ này bị giới hạn bởi cửa sổ dữ liệu và định danh nguồn; không gọi nhóm một đơn là churn, không suy ra customer lifetime value tương lai.

Cohort dựa trên lần mua delivered đầu được quan sát; khách được đếm distinct lại trong từng tháng tuổi cohort. Mỗi cell chia cho cohort size gốc; chỉ tạo cell nằm trong cửa sổ đã quan sát. Các ô không có hoạt động trong cửa sổ là 0, ô tương lai không được tạo.

| frequency_segment | customers | delivered_orders | observed_merchandise_value |
| --- | --- | --- | --- |
| 1 delivered order | 90,557 | 90,557 | 12,493,089.36 |
| 2 delivered orders | 2,573 | 5,146 | 631,274.90 |
| 3+ delivered orders | 228 | 775 | 97,133.85 |

## 4. Giao hàng và thanh toán có gì đáng chú ý?

Trong tháng có **6,156** đơn đủ điều kiện ngày giao; **5,948** đơn đúng hẹn (**96.62%**). Ngày hứa giao được so theo ngày lịch, đúng quy tắc fact. Các bang có ít quan sát cần được xem cùng sample size; không xếp hạng chỉ từ trung bình.

| buyer_state | eligible_deliveries | on_time_rate | median_delivery_days |
| --- | --- | --- | --- |
| SP | 2,712 | 96.31% | 5.79 |
| RJ | 696 | 97.56% | 8.06 |
| MG | 644 | 98.76% | 7.15 |
| PR | 314 | 98.09% | 7.37 |
| RS | 308 | 98.38% | 9.31 |
| BA | 245 | 93.88% | 12.14 |
| SC | 195 | 97.95% | 8.29 |
| DF | 165 | 95.76% | 7.91 |

| payment_method | payment_records | orders_using_method | recorded_payment_value |
| --- | --- | --- | --- |
| credit_card | 4,755 | 4,738 | 803,674.49 |
| boleto | 1,229 | 1,229 | 198,041.24 |
| debit_card | 242 | 242 | 44,866.18 |
| voucher | 281 | 212 | 19,958.84 |

Payment records không phải số đơn: một đơn có thể có nhiều records/phương thức. Recorded amount có thể gồm freight hoặc thuộc trạng thái khác; không gọi đây là doanh thu thuần, tiền đã thu hay refunds.

## 5. Chất lượng dữ liệu có làm sai kết luận không?

| rule_id | severity | affected_records |
| --- | --- | --- |
| DQ-CAT-001 | warning | 610 |
| DQ-COV-001 | warning | 775 |
| DQ-COV-002 | warning | 1 |
| DQ-PAY-001 | warning | 303 |
| DQ-TIME-001 | warning | 8 |
| DQ-TIME-002 | warning | 166 |

Những cảnh báo này được giữ nguyên từ nguồn. Lỗi schema/grain/relationship/parity mới chặn publication. Thiếu items/payment không bị tự điền tiền để cân số. Không cộng affected occurrences giữa các rule thành số bản ghi lỗi phân biệt.

## 6. Tái lập và giới hạn

`make analyze` chạy SQL trong `analysis/sql/`, EXPLAIN trước execute, ghi CSV, query SHA và kiểm oracle vào `var/analysis/results.json`. Notebook đi kèm đọc chính các CSV đã xuất. Các core KPI đối soát với MetricFlow; cohort/recency/payment là governed SQL analysis và không được trình bày như metric MetricFlow mới.

Nguồn: Olist v2, CC BY-NC-SA 4.0; portfolio độc lập. BRL là quy ước vì CSV không có currency. Không có tên khách/sản phẩm, chi phí, clinical/telesales hoặc lịch sử trạng thái tại ngày mua. Phân tích mô tả các quan sát trong snapshot, không đại diện tình hình hiện tại của Abbott/Concentrix.
