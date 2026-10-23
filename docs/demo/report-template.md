# Sales and Customer Analytics Warehouse

**Báo cáo dự án portfolio Data Engineer**

Bản giao trình bày ngày $date. Dự án độc lập với dữ liệu Olist công khai, phục vụ demo năng lực tích hợp dữ liệu, thiết kế Warehouse Kimball, quản trị KPI và vận hành pipeline trên máy cá nhân.

### Tóm tắt kết quả

Hệ thống đã xử lý 451.535 dòng từ 7 feed, xây 7 dimensions và 3 facts trên PostgreSQL bằng dbt, thực thi 8 KPI lõi bằng MetricFlow và cung cấp 6 dashboard Superset. Airflow điều phối 9 stage; dữ liệu chỉ được công bố sau các kiểm tra về grain, quan hệ, số tiền và semantic parity.

| Hạng mục | Kết quả đã có |
|---|---|
| Dữ liệu kinh doanh | 99.441 orders; 112.650 order items; 103.886 payment records |
| Mô hình phân tích | Kimball bus; conformed dimensions; integer dimension SK; transaction và accumulating snapshot facts |
| Đầu ra nghiệp vụ | Tổng quan và 5 trang chuyên sâu; 60 đối tượng báo cáo; 8 saved SQL analyses; notebook và CSV |
| Semantic | 5 MetricFlow exports, đối chiếu generated SQL, native CLI và SQL oracle độc lập |
| Kiểm chứng vận hành | Retry, terminal failure, replay, late-arrival và DWH restore có bằng chứng riêng |

### Giá trị của dự án

Business/BA có một bộ số liệu thống nhất để tìm hiểu bán hàng, danh mục, khách hàng và giao hàng. Data Engineer có thể truy từ báo cáo về release, model, source version và bản gốc; chạy lại không nhân đôi dữ liệu nghiệp vụ và giữ bản công bố trước khi candidate lỗi.

**Phạm vi là local demo đã triển khai, không phải hệ thống production hoặc kiến trúc nội bộ Abbott, Concentrix hay Mắt Bão.** Dữ liệu không thuộc ngành dược và không có telesales trong v1. Đây là cách minh họa các năng lực DE có thể chuyển sang một bối cảnh doanh nghiệp khác, không khẳng định đã biết dự án nội bộ của nhà tuyển dụng.

### Cách đọc bộ tài liệu

Trang 2 mô tả bài toán và nguồn; trang 3–6 là kiến trúc, workflow và Kimball; trang 7–8 là semantics và chất lượng; trang 9–10 là đầu ra; trang 11–13 là kiểm chứng, vận hành và nguồn tham chiếu. Bộ sơ đồ 10 trang riêng phù hợp để chiếu khi phỏng vấn.

<!-- pagebreak portrait -->

## 1 Bài toán và dữ liệu đầu vào

### Các câu hỏi cần trả lời

- Quy mô bán hàng theo tháng thay đổi thế nào, do số đơn, AOV hay cơ cấu nào cần xem tiếp?
- Danh mục, seller và khu vực nào đóng góp lớn vào giá trị hàng đã giao?
- Bao nhiêu khách có mua lại trong cửa sổ quan sát? Các cohort có đủ thời gian để so sánh chưa?
- Giao đúng hẹn và thời gian giao ra sao, trên bao nhiêu đơn đủ mốc ngày?
- Dữ liệu có cảnh báo gì, đến từ release nào và pipeline gần đây hoạt động thế nào?

### Nguồn có thật và đủ quan hệ

Nguồn là Brazilian E-Commerce Public Dataset by Olist, version 2. Bảy file là bảy domain feed của một nhà công bố, không phải bảy hệ thống độc lập. ZIP 44.717.580 bytes được giữ nguyên, có SHA-256 và manifest. Reviews/geolocation còn trong archive gốc nhưng ngoài xử lý v1.

| Feed | Số dòng | Vai trò |
|---|---|---|
| Customers | 99.441 | Tham chiếu khách và địa chỉ theo đơn |
| Orders | 99.441 | Trạng thái và các milestone của đơn |
| Order items | 112.650 | Dòng hàng, giá, freight, product và seller |
| Payments | 103.886 | Payment record, phương thức và installments |
| Products | 32.951 | Mã sản phẩm và thuộc tính nguồn |
| Sellers | 3.095 | Mã seller và địa lý |
| Category translation | 71 | Chuẩn hóa tên category tiếng Anh |

### Những giới hạn quyết định cách thiết kế

`customer_id` là tham chiếu theo đơn; `customer_unique_id` mới là identity khách bền vững. Không có tên khách hoặc tên sản phẩm để tự bổ sung. Source timestamp không có timezone offset; operational clocks dùng UTC. BRL là quy ước demo vì CSV không có trường currency.

Nguồn hiện là snapshot lịch sử, không có `source_updated_at`, CDC hoặc lịch sử trạng thái đầy đủ. Baseline live được nhận theo full-v2 tại source cut 1. Incremental, late-arrival và correction được kiểm bằng delivery plan/fixture có nhãn riêng trong database cô lập, không giả thành giao dịch mới của Olist.

<!-- pagebreak landscape -->

## 2 Kiến trúc thực tế đang chạy

![Kiến trúc implementation hiện tại theo Docker Compose và stage CLI](png/02-system-architecture.png)

Đọc theo số 01–08: hàng trên trái sang phải, hàng dưới phải sang trái. Có 7 dịch vụ thường trực; dbt/MetricFlow chạy theo task. Metadata ứng dụng tách database. Không có OLTP hoặc streaming; Superset không đọc mutable work. MinIO giữ raw, không phải Delta/Iceberg lakehouse.

<!-- pagebreak landscape -->

## 3 Workflow và trách nhiệm của Airflow

![DAG thực tế gồm raw validate load lease build snapshot semantic publish finish](png/06-airflow-workflow.png)

DAG có `catchup=false`, một active run và timeout 15 phút/task. Lịch có thể chạy nhiều lần nhưng nguồn tĩnh không tự sinh giao dịch mới. Superset handoff không thuộc 9 task; URL pin giữ bản đã chọn khi pipeline công bố bản khác. Mũi tên nét đứt là bước bàn giao riêng.

<!-- pagebreak landscape -->

## 4 Kimball bus và các business process

![Bus matrix biểu diễn dimensions dùng chung và grain từng process](png/04-kimball-bus-matrix.png)

Bus tích hợp các star, không thay thế star schema. Registry giữ integer dimension SK ổn định; Unknown = 0, N/A = -1. `order_id` là degenerate dimension. Payment date chỉ là purchase context; không phân bổ payment về product/seller. Aggregate riêng facts rồi drill-across để tránh fanout.

<!-- pagebreak landscape -->

## 5 Khóa và quan hệ trong Warehouse

![Schema rút gọn từ migration với 7 dimensions và 3 facts](png/10-warehouse-key-schema.png)

Mọi FK cùng `release_id`; dimension SK là bigint, date key là int. Fact identity là text với unique business grain riêng. Bốn đường routing chung không phải một bảng bus vật lý; giao nhau không biểu diễn join. File `warehouse-schema.mmd` đi kèm có từng FK cụ thể; migration 001 là nguồn cột/constraint.

<!-- pagebreak portrait -->

## 6 Semantic Layer và lớp phục vụ

### Một định nghĩa KPI có thể thực thi

dbt chứa semantic models/metric definitions. Local MetricFlow đọc views được bind vào một candidate release, sinh và chạy SQL PostgreSQL, rồi ghi 5 bảng export trong `reporting`. Kết quả có query hash, manifest và oracle parity trước khi publish. Không dùng semantic API trả phí và không sửa SQL do engine sinh để giả tương thích.

| KPI | Định nghĩa | Grain và giới hạn |
|---|---|---|
| total_orders | Tổng order_count | Mỗi accepted order tính một lần |
| delivered_orders | Tổng delivered_order_count | Theo accepted source status |
| canceled_orders | Tổng canceled_order_count | Không suy ra lý do hủy |
| cancellation_rate | canceled / total orders | Mẫu số 0 trả NULL |
| delivered_merchandise_value | Tổng giá item của delivered orders | Chưa gồm freight; không gọi là profit |
| delivered_aov | Delivered merchandise / delivered orders | Tính lại tử/mẫu ở grain cần hỏi |
| delivered_unique_customers | Distinct durable customer của delivered orders | Không cộng distinct theo ngày hoặc bang |
| delivered_item_rows | Tổng item_row_count của delivered orders | Đếm dòng hàng, không suy diễn quantity |

### Khi nào lưu bảng mới và khi nào tính trong fact

Atomic facts giữ số đo đúng grain nguồn và các order-level summaries đã có hợp đồng. Derived ratios và distinct được định nghĩa ở semantic/query layer, không ghi một AOV hoặc tỷ lệ vào mọi fact row. Khi phục vụ BI, exports lưu kết quả tổng hợp theo ngày, tháng, category, seller hoặc buyer state và có `release_id`.

Các bảng reporting này là serving aggregates trong cùng PostgreSQL, không phải một DWH khác. Implementation hiện không mô hình chúng thành một bus aggregate-star riêng có đầy đủ dimension SK; không nên gọi chúng như vậy. Không được SUM các tỷ lệ hoặc distinct để roll up.

### Hai đường dữ liệu vào Superset

Core KPI lấy từ 5 validated MetricFlow exports. Customer/cohort/delivery/payment dùng governed `reporting.analytic_*` SQL views trên published Kimball, có grain, cutoff và independent checks riêng. Đây là SQL analytics bổ sung, không phải các metric MetricFlow mới hoặc native Superset–MetricFlow connector.

<!-- pagebreak portrait -->

## 7 Chất lượng và công bố dữ liệu

### Không xóa cảnh báo nguồn để có báo cáo đẹp

Những bất thường có sẵn được giữ và mô tả. Parent order vẫn tồn tại khi thiếu children, kèm completeness flags; không tự điền tiền để cân sổ. Cảnh báo nguồn không đồng nghĩa pipeline transformation bị sai.

| Cảnh báo nguồn | Số lượng | Xử lý và ảnh hưởng |
|---|---|---|
| Order không có items | 775 | Giữ order; không bịa merchandise value |
| Order không có payment | 1 | Giữ order và flag thiếu payment |
| Product thiếu category | 610 | Giữ product identity và unknown category |
| Delivered thiếu delivery timestamp | 8 | Vẫn tính delivered; loại khỏi eligibility về ngày giao |
| Matched order lệch payment trên 0,01 | 303 | Ghi warning, không sửa source amount |
| Temporal anomaly | 166 | Ghi diagnostic và kiểm eligibility trước phân tích thời gian |

Các occurrence giữa rule có thể chồng lấn; không cộng chúng thành số bản ghi lỗi phân biệt. Error về schema, conflict, grain, relationship, invariant hoặc semantic parity phải chặn batch/candidate theo contract.

### Release isolation bảo vệ người xem báo cáo

Working models được build trên một fixed source cut. Snapshot Kimball có typed constraints và logical hashes; semantic connections phải bind đúng release. Publisher kiểm toàn bộ gates và lease fencing trước khi ghi trạng thái published/pointer trong một PostgreSQL transaction.

Superset chỉ đọc published reporting views bằng role readonly và mọi chart của một dashboard cùng pin release. Candidate lỗi không làm chart đọc nửa bộ dữ liệu. Đổi publication pointer không tự thay URL BI đang mở; cập nhật assets là bước bàn giao riêng, không nằm trong giao dịch Warehouse.

### Truy vết và bảo vệ dữ liệu

Lineage nối source archive/file/row/version tới model, snapshot và generated metric query. Role BI không đọc landing, mutable work hoặc ghi exports. UI chỉ mở loopback, PostgreSQL không publish host port; credentials không nằm trong bộ tài liệu này. Đây là ranh giới local trust, không phải chứng nhận pentest hoặc bảo mật production.

<!-- pagebreak portrait -->

## 8 Kết quả phân tích có thể trình bày

**Kỳ kinh doanh $month; customer cutoff 31/08/2018.** Tất cả số liệu bên dưới dùng cùng release handoff, không gộp các cửa sổ phân tích khác nhau thành một KPI.

| Chỉ số | Kết quả | Cách hiểu |
|---|---|---|
| Giá trị hàng delivered | $value BRL | Merchandise; chưa gồm freight |
| Delivered orders | $orders | Trong 6.292 total orders của tháng |
| Distinct delivered customers | $customers | Đếm lại tại grain tháng |
| Delivered AOV | $aov BRL/đơn | Tử số merchandise / số đơn delivered |
| Cancellation rate | $cancel% | 41 canceled / 6.292 orders |
| Merchandise MoM và YoY | +$mom% / +$yoy% | So đúng kỳ; không kết luận nhân quả |
| Giao đúng hẹn | $ontime% | 5.948 / 6.156 đơn đủ mốc ngày |

### Đâu là khu vực cần đi sâu

Category `health_beauty` dẫn đầu tháng với 103.524,22 BRL, chiếm 11,93%; top 10 seller chiếm 14,15%. Có thể mở trang sản phẩm/seller để kiểm tra cơ cấu và tập trung đóng góp, nhưng chưa có inventory/cost để suy ra thiếu hàng hoặc lợi nhuận.

Trong toàn cửa sổ khách hàng đến cutoff, 2.801/93.358 khách có từ hai đơn delivered, tương đương 3,00%, đóng góp 5,51% giá trị quan sát. Không gọi khách một đơn là churn; chỉ so cohort có cùng độ tuổi và đủ thời gian quan sát. Ô tương lai chưa có quan sát không được biến thành 0% retention.

Giao hàng tháng có 6.156/6.159 delivered orders đủ ngày. Khi so bang phải xem sample size và độ phủ cùng tỷ lệ/median; không xếp hạng chỉ từ trung bình. Payment records không phải orders và recorded payment không mặc định là recognized revenue hoặc tiền đã thu.

### Phân tích có thể tái lập

`analysis/sql/` có 8 truy vấn; lệnh analyze EXPLAIN trước execute, đối chiếu oracle và xuất CSV/query hashes. Notebook đọc lại CSV đã đối soát, không cần secret DB. File `business-analysis.md` đi kèm giải thích phát hiện và giới hạn đầy đủ. Kỳ cuối 08/2018 có thể thiếu quan sát; không dùng nó để kết luận doanh nghiệp đang suy giảm.

<!-- pagebreak landscape -->

## 9 Bộ dashboard theo câu hỏi nghiệp vụ

| Trang Superset | Câu hỏi nghiệp vụ | Phạm vi phân tích |
|---|---|---|
| Tổng quan kinh doanh | Kinh doanh thế nào và cần xem sâu ở đâu? | 8 KPI, 4 biểu đồ, 3 điểm nhấn; điểm vào của suite |
| Hiệu quả bán hàng | Giá trị, đơn, khách và AOV thay đổi thế nào? | Tháng chọn; xu hướng 01/2017–08/2018 giữ ngữ cảnh |
| Sản phẩm và nhà bán hàng | Category/seller/khu vực nào đóng góp lớn? | Item-grain và cơ cấu giá trị theo tháng |
| Khách hàng và mua lại | Repeat/recency/cohort cho thấy gì? | Toàn kỳ đến 31/08/2018; không cắt lịch sử theo tháng menu |
| Giao hàng và thanh toán | Giao đúng hẹn, thời gian giao và payment mix ra sao? | Tháng mua; đúng eligibility và payment grain |
| Chất lượng và vận hành | Nguồn, release, cảnh báo và run nào tạo ra số liệu? | Producer/release pin; lịch sử audit được phân biệt riêng |

48 KPI/plots + 6 bảng Điểm nhấn + 6 menu = 60 đối tượng đang gắn vào 6 dashboard. Đây không phải 60 KPI nghiệp vụ riêng. Mỗi trang có nhận xét query-backed, kết quả và gợi ý kiểm tra; phương pháp dài nằm trong mô tả biểu đồ/tài liệu thay vì lặp trên giao diện.

Chọn tháng rồi Apply filters; nhận xét thay số cùng tháng trên overview, sales, commercial, service. Menu giữ tháng và release khi chuyển trang. Trên customer/trust, tháng chỉ điều hướng, không thay cutoff khách hàng hoặc producer. Đây là report navigation, không phải order-level drill-through hoặc mang mọi cross-filter chưa có hợp đồng.

Ảnh sáu trang thật nằm trong `screenshots/` của kit. Mở `index.html` để xem hình kỹ thuật offline; mở URL Superset trong demo để thấy filter và navigation hoạt động thật. Ảnh này chỉ chứa published aggregates, không chứa mật khẩu hoặc raw customer records.

### Điểm bắt đầu khi trình diễn

[Mở Tổng quan Superset](http://localhost:18088/superset/dashboard/olist-overview-87f01740/). Đọc tháng 07/2018, đổi sang 06/2018, mở Sản phẩm/seller rồi quay về Tổng quan. Sau đó mở Khách hàng để giải thích cutoff riêng và Chất lượng để chỉ nguồn/release. Không nói menu đang drill-through tới từng đơn hàng.

<!-- pagebreak portrait -->

## 10 Bằng chứng kiểm chứng và phạm vi

Kiểm tra UI/health được xác nhận trong lần khởi động ngày $health_date. Runtime DE/recovery/restore dưới đây là bằng chứng lịch sử ngày 15/10/2026 và refinement BI ngày 16/10/2026; việc xuất báo cáo không chạy lại ingestion hoặc biến mọi gate thành nghiệm thu production.

| Kiểm chứng | Kết quả có bằng chứng | Phạm vi hoặc giới hạn |
|---|---|---|
| Source và raw | Archive checksum, 7 feed; S3 PUT/GET và source fallback | Hash/file/profile không thay bằng chứng DB |
| dbt và Kimball | 18 models + 75 tests = 93 nodes; 10 snapshot relations | Grain/FK/money/counts/lineage được kiểm riêng |
| Semantics | 8 core metrics, 5 exports có native CLI/SQL parity | Không gọi SQL cohort là MetricFlow metric |
| Superset hiện tại | 60 chart queries + 8 saved queries thành công | 6 trang render; nhận xét và filters có kiểm |
| Navigation hiện tại | 14 actual clicks, 1720/1366 px, 8 KPI overview vừa viewport đầu | Customer/trust giữ scope riêng |
| Airflow lịch sử | Load thử 2 thành công; raw terminal fail sau 3 lần | DAG/ledger failed, downstream upstream_failed |
| Incremental và replay | 0 new versions khi replay; late child tính lại parent; SK ổn định | Isolated target; delivery sequence simulated |
| Recovery | Load commit giữ được; snapshot/export rollback; parity chặn publish; ACK recovery | Không chỉnh pointer live bằng SQL để giả tình huống |
| DWH restore | $restore giây; signatures/keys/KPI/pointer/ACL khớp | Target mới; live không bị ghi đè; không phải app restore |
| Publication pinning | Browser giữ bản cũ khi bản mới publish | Drill cũ chỉ gồm 10 sales charts ban đầu |

### Không đánh đồng các loại bằng chứng

137 design/source/fixture/DDL checks và 5 offline semantic cases là kiểm chứng offline, không phải số kiểm thử runtime. 20 REQ/V contracts là phạm vi đặc tả, không ngụ ý toàn bộ subcriteria đã nghiệm thu. Test fixture SCD2 chứng minh xử lý explicit effectivity, không tạo lịch sử Type 2 thật từ Olist.

Manifest kit lưu SHA-256 input và output, release và phạm vi. Không dùng ảnh Metabase cũ làm bằng chứng Superset; bộ này chỉ đưa ảnh Superset hiện hành. Mốc restore là một lần đo trên host, không phải RTO cam kết của doanh nghiệp.

<!-- pagebreak portrait -->

## 11 Vận hành và kịch bản demo

### Khởi động máy đã cài đặt

Chạy `make start verify-boot`; dbt Docs dùng Compose profile docs. Không chạy `make demo` chỉ để mở lại giao diện vì lệnh đó gồm build/provision/pipeline/handoff. Không cần nạp lại dữ liệu trước mỗi buổi trình bày.

| Giao diện | Địa chỉ local | Mục đích |
|---|---|---|
| Superset | localhost:18088 | Báo cáo nghiệp vụ và SQL Lab |
| Airflow | localhost:18080 | DAG, tasks, retries và logs |
| dbt Docs | localhost:18081/static_index.html | Model docs và lineage |
| MinIO console | localhost:19001 | Bản raw và object metadata |

Credential chỉ tồn tại trong file private local theo runbook; không đưa mật khẩu vào PDF, ảnh, slide hoặc repository. Superset đọc Warehouse bằng role BI riêng; tài khoản admin giao diện không đồng nghĩa có quyền raw/work trong database.

### Lộ trình trình bày khoảng 7 phút

- Phút 0–1: bài toán, dữ liệu Olist thật và đầu ra đã có; xác định rõ dự án portfolio.
- Phút 1–2: hình kiến trúc; giải thích nguyên nhân cần landing, dbt và published snapshot.
- Phút 2–3: bus matrix và một star; grain, integer SK, conformed dimensions, không fact fanout.
- Phút 3–4: Airflow và semantic; phân biệt metric definition, export table và dashboard.
- Phút 4–6: Tổng quan Superset, đổi tháng và chuyển trang; đọc nhận xét từ dữ liệu thật.
- Phút 6–7: mở test evidence/retry logs; nêu replay/restore đã kiểm trong sandbox và các giới hạn.

Không chạy fault injection, destructive SQL hoặc restore đè live để trình bày. Nếu cần tái hiện failure, dùng target cô lập và quy trình được duyệt riêng. Không clear failed ledger run để biến lịch sử thành thành công.

### Ranh giới của bản demo

Single-host, không HA/DR site; local backup chưa mã hóa/off-host nên không bảo vệ mất máy. Superset app restore, remote CI, clean-room host thứ hai, external alert receiver và SLO soak test chưa nghiệm thu. Retention hiện là inventory-only; không tự xóa raw, releases hoặc Docker volumes. Không giới thiệu đây là production-ready.

<!-- pagebreak portrait -->

## 12 Nguồn tham chiếu và provenance

### Danh tính bộ dữ liệu và bản báo cáo

- Dataset: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), version 2. Metadata được lưu tại `data/source-manifest.json`; Olist CC BY-NC-SA 4.0. Giữ attribution và điều kiện áp dụng cho derived data; không suy ra quyền triển khai thương mại của khách hàng.
- Release handoff: `$release`.
- Producer pipeline run: `$producer`; source cut 1.
- Kỳ kinh doanh mặc định $month; customer cutoff 2018-08-31. Ngày xuất tài liệu $date không phải ngày phát sinh dữ liệu kinh doanh.

SHA-256 raw archive được ghi đầy đủ trong manifest kit và `data/source-manifest.json`. Không đưa raw ZIP hoặc customer-level records vào bộ gửi nhà tuyển dụng.

### Các tài liệu và code có thể đối chiếu trong repository

| Nhóm | Đường dẫn nguồn |
|---|---|
| Quyết định và phạm vi | README.md; docs/implementation-progress.md; docs/analytics-design.md |
| Kiến trúc chạy thật | infra/compose.yaml; orchestration/dags/sales_warehouse_pipeline.py; src/sales_dw/cli.py |
| Kimball | contracts/warehouse-model.json; db/migrations/001_schema.sql; docs/warehouse-erd.md |
| KPI và analytical SQL | dbt/models/semantic/semantic_models.yml; src/sales_dw/export_metrics.py; db/migrations/005_published_analysis.sql |
| Dữ liệu và phân tích | docs/evidence/source-profile.json; output/analysis/results.json; analysis/sql/ |
| Evidence UI gần đây | var/evidence/superset.json; superset-browser.json; health.json |
| Evidence lịch sử | docs/evidence/runtime/: airflow, incremental, pipeline-recovery, restore và runtime-sales_dw reports |
| Hướng dẫn vận hành | docs/runtime-runbook.md; docs/superset-demo-guide.md |

Các đường dẫn `var/` là evidence private trên máy demo, không phải tài nguyên được mặc định chia sẻ. Manifest kit ghi hash của input để truy xuất; không sao chép nội dung private tùy ý. Bộ ảnh, Markdown, PDF và screenshot aggregate trong ZIP là allowlist để gửi.

### Điều dự án chứng minh

Khả năng đi từ câu hỏi nghiệp vụ tới source contract, grain/model, SQL transformation, executable semantics, quality gates, orchestration và đầu ra người dùng kiểm chứng được. Các nguyên tắc đó có thể áp dụng khi nguồn và công nghệ doanh nghiệp thay đổi; dự án không tuyên bố biết hệ thống nội bộ hoặc đã tạo lợi ích tài chính chưa đo.
