# Superset — báo cáo và bộ phân tích cho demo

Superset là UI chính theo quyết định mới. Hệ thống dùng Docker Compose project `salesdw`, cùng Warehouse Kimball và semantic exports đã kiểm chứng. Phạm vi dừng ở demo local. Metabase cũ được giữ như lịch sử; không cần nó để xem bộ báo cáo mới.

## Đăng nhập và đọc báo cáo

Mở http://localhost:18088, username `demo`, mật khẩu trong file private `var/secrets/superset_admin.json`. Superset có database metadata riêng `superset_meta`; kết nối Warehouse dùng role `salesdw_bi` chỉ đọc published views. Không copy password hoặc connection URI vào tài liệu chia sẻ.

| Báo cáo | Đường dẫn của release handoff | Câu hỏi |
|---|---|---|
| **Tổng quan kinh doanh — bắt đầu ở đây** | http://localhost:18088/superset/dashboard/olist-overview-87f01740/ | Quy mô, biến động, đóng góp và giao hàng; cần mở trang nào để điều tra tiếp? |
| Hiệu quả bán hàng | http://localhost:18088/superset/dashboard/olist-sales-87f01740/ | Giá trị hàng, số đơn/khách, AOV, hủy đơn, MoM/YoY và xu hướng |
| Sản phẩm & nhà bán hàng | http://localhost:18088/superset/dashboard/olist-commercial-87f01740/ | Category/seller nào đóng góp lớn; cơ cấu và khu vực người mua |
| Khách hàng & mua lại | http://localhost:18088/superset/dashboard/olist-customers-87f01740/ | Mua lại, recency và cohort theo cửa sổ quan sát |
| Giao hàng & thanh toán | http://localhost:18088/superset/dashboard/olist-service-87f01740/ | Đúng hẹn, thời gian giao, phương thức và số kỳ thanh toán |
| Chất lượng dữ liệu & vận hành | http://localhost:18088/superset/dashboard/olist-trust-87f01740/ | Release/source cut nào, producer run, cảnh báo nguồn và các run thất bại |

Native filter chọn **một tháng** rồi bấm **Apply filters**. Mặc định là 2018-07. KPI/daily/breakdown đổi theo tháng; xu hướng Sales giữ 01/2017–08/2018 để cung cấp ngữ cảnh. Customer Behavior dùng toàn kỳ đến 31/08/2018, không cắt lịch sử khách theo bộ lọc tháng.

## Luồng trình bày theo câu hỏi BA

Chọn **tổng quan → trang chuyên sâu**, không nhét mọi biểu đồ vào một trang dài. Trang tổng quan có 8 KPI, 4 biểu đồ, 3 nhận xét từ truy vấn và menu sáu trang. Toàn bộ suite có 60 đối tượng đang sử dụng: 48 KPI/biểu đồ, 6 bảng nhận xét và 6 menu điều hướng. Metadata lịch sử được giữ, nên tổng số chart trong trang quản trị có thể lớn hơn 60.

1. Bắt đầu ở Tổng quan, chọn tháng mua, bấm Apply filters. Đọc giá trị hàng/đơn/khách/AOV cùng thay đổi tháng trước, hủy đơn và giao hàng đủ điều kiện.
2. Đọc ba câu trả lời: bán được bao nhiêu và thay đổi ra sao; category nào dẫn đầu; giao hàng ra sao và đo được bao nhiêu. Đây là mô tả quan sát, không phải kết luận nhân quả.
3. Bấm **Bán hàng** để xem chi tiết biến động; **Sản phẩm & seller** để xem cơ cấu/đóng góp; **Giao & thanh toán** để kiểm tra vận hành. Menu mang tháng đang chọn và giữ nguyên release.
4. Bấm **Khách hàng** để đọc repeat/cohort toàn kỳ; **Chất lượng dữ liệu** để xem release, producer, cảnh báo và audit. Trên hai trang này, **Tháng chuyển trang** chỉ chọn tháng mang sang các liên kết, không đổi cửa sổ lịch sử khách hay producer đã pin.
5. Bấm **Tổng quan** trong menu để quay lại; có thể chuyển thẳng giữa các trang con mà không trở về danh sách dashboard. Tháng đã chọn vẫn được giữ.

Link menu là điều hướng giữa các báo cáo, không phải drill-through tới từng đơn hàng và không tự mang category/state chưa có hợp đồng filter tương thích. Không có budget, cost hay SLA mục tiêu trong nguồn nên không dựng chỉ báo đỏ/xanh hoặc nhãn đạt/trượt giả.

## Dashboard trả lời gì và dùng kết quả thế nào?

Giao diện ưu tiên số liệu: một dòng ngữ cảnh ngắn → menu nút → KPI → **Điểm nhấn** → biểu đồ. Các khối giới thiệu, hướng dẫn và disclaimer dài lặp lại đã được bỏ theo phản hồi người dùng (ADR-016). Cuối trang chỉ giữ ghi chú ngắn về nguồn/đơn vị/định nghĩa cần thiết. Bảng Điểm nhấn vẫn trả kết quả truy vấn thật theo kỳ, không phải caption ghi tay.

Định nghĩa, cách đọc và giới hạn đầy đủ nằm trong mô tả biểu đồ và tài liệu này; release/source cut/producer được xem ở trang Chất lượng dữ liệu. Không cần hiển thị SQL Lab hoặc mã release trên mọi trang kinh doanh. Bộ lọc tháng và các phép tính vẫn giữ nguyên; việc rút gọn giao diện không thay đổi dữ liệu.

| Trang | Ví dụ kết quả đã kiểm | Cách diễn giải / bước tiếp |
|---|---|---|
| Sales, 07/2018 | 867.953,46 BRL delivered merchandise; MoM +1,39%, YoY +80,22% | So thêm số đơn, AOV, cơ cấu và độ đầy đủ kỳ; chưa khẳng định nguyên nhân tăng |
| Products & Sellers, 07/2018 | health_beauty đứng đầu 11,93%; top 10 seller 14,15% giá trị | Chọn nhóm đóng góp lớn để kiểm tra; không suy ra profit hay thiếu hàng |
| Customers, đến 31/08/2018 | 2.801/93.358 khách mua lại ≈3,00%, đóng góp 5,51% giá trị | So cohort cùng độ tuổi; không gọi khách một đơn là churn. M1 riêng: 420/86.950 ≈0,48%, 19 cohort từ 2017 đủ quan sát |
| Delivery & Payments, tháng mua 07/2018 | 5.948/6.156 đơn đủ điều kiện đúng hẹn ≈96,62%; median 7,5 ngày | Đọc cùng độ phủ 6.156/6.159 delivered; xem sample size theo bang trước khi ưu tiên kiểm tra |
| Data Trust, release 87f01740 | Producer succeeded, 0 error occurrences, 6 warning rules có ảnh hưởng | Không hiểu 0 error là nguồn sạch tuyệt đối; mở rule và lineage, tách producer đã pin khỏi lịch sử audit live |

Các ví dụ trên có kỳ/release cố định để trình bày. **Bảng nhận xét trên UI thay số liệu thật khi đổi tháng** ở Tổng quan, Sales, Products & Sellers và Delivery & Payments. Customer giữ cutoff của riêng trang; Trust giữ producer/release. Không có mẫu số/kỳ trước phù hợp thì hiển thị “không đủ dữ liệu”, không biến thành 0%.

Heatmap hiển thị cohort 2017 trở đi, tháng tuổi 1–6; M0 luôn là 100% nên được bỏ khỏi vùng màu để thấy khác biệt các lần quay lại. Ô chưa có đủ thời gian quan sát để trống; mẫu số là cohort size gốc. SQL/CSV đầy đủ vẫn giữ M0 và các cohort nhỏ năm 2016.

SQL → Saved queries chứa 8 truy vấn tương ứng `analysis/sql/`. Mỗi query đã bind release và tháng; có thể mở vào SQL Lab để đọc/chạy lại bằng kết nối readonly. Không suy ra quyền truy cập raw/work/facts trực tiếp từ quyền Admin UI.

## Bộ phân tích

[Báo cáo tiếng Việt](../output/analysis/business-analysis.md) có phát hiện được tính thật, so sánh tháng, concentration, repeat customer, delivery/payment và giới hạn kết luận. [Notebook](../output/analysis/analysis.ipynb) đọc lại các CSV cùng thư mục. [Kết quả máy đọc](../output/analysis/results.json) ghi queries/checks/release/cutoff; mã SQL gốc ở `analysis/sql/`.

Ví dụ tháng 2018-07 đã kiểm: merchandise 867.953,46 BRL, 6.159 delivered orders, 6.100 distinct customers, AOV 140,92. Repeat observed customers 2.801/93.358 ≈3,00%, đóng góp khoảng 5,51% merchandise toàn kỳ. Đây là số đo snapshot, không phải causal churn, dự báo hoặc dữ liệu Abbott.

## Khởi động và tái tạo

```bash
make prepare build
make up
make source run
make verify-bi
make analyze
make verify-browser
python scripts/package_analytics.py
make verify-boot verify-runtime
```

Máy đã cài: `make start`. `make verify-bi` resolve published pointer một lần, tạo assets riêng theo release và query mọi chart. Publication mới không tự đổi assets/URL đang mở. Khi muốn xem release mới, chạy lại verify-bi và dùng links trong `var/bi/superset-state.json`.

Khi chỉ sửa giao diện/menu và muốn giữ release hiện tại: **`make refresh-bi`**. Lệnh chạy bootstrap hai lần, kiểm IDs/counts không tạo trùng rồi query toàn bộ chart. Sau đó `make verify-browser` kiểm sáu trang và bấm các đường điều hướng thật. Không cần chạy lại ingestion/dbt hay migration cho thay đổi trình bày này.

Migration thêm SQL views là `db/migrations/005_published_analysis.sql`; đi qua `scripts/migrate.py --superset` (plan), rồi `--apply --approved-project salesdw --superset`. Superset metadata migrations đi qua designated `superset-init`. Không chỉnh migration đã áp dụng để sửa lỗi.

## Kiểm chứng và trade-offs

API verification chạy 60 chart objects, đối chiếu KPI với MetricFlow exports/customer SQL và số trong từng nhận xét với analytical SQL/arithmetic riêng. Kiểm thêm tháng 06/2018 trên cả bốn trang theo tháng, overview/sales thiếu kỳ so sánh và tháng không có delivered orders. Kiểm sáu menu cho tháng 06/07, cùng release, đúng URL/filter state và bootstrap idempotency. Browser verification mở đủ sáu trang, kiểm nhận xét hiện đủ và không bị cắt ngang, actual SQL/native month change trên cả bốn trang theo tháng, trend context, JavaScript/render errors; bấm 14 lượt overview→detail→overview và giữa các trang con; kiểm customer/trust không đổi cửa sổ, cùng hai độ rộng 1720/1366. Bộ phân tích đối chiếu tám core metrics với order grain, cohort oracle, customer/value totals và payment grain.

Refinement nhận xét/tổng quan/điều hướng chỉ thêm virtual datasets/charts và bố cục vào metadata Superset; không sửa nguồn, core metric hay migration DWH. Chứng cứ concurrent publication cũ vẫn giữ scope 10 sales charts ban đầu; không dùng nó để tuyên bố đã chạy lại publication drill cho menu, trang tổng quan hay các bảng nhận xét mới.

Superset local dùng hai Gunicorn workers, cache trong bộ nhớ, query synchronous và chỉ bind loopback. Đây là lựa chọn demo theo workload, không phải cấu hình production. Backups/app restore/credential rotation của Superset chưa tự động được nghiệm thu chỉ từ bằng chứng Metabase cũ. `make backup` có thêm metadata Superset; thông tin đăng nhập và SECRET_KEY vẫn phải được giữ riêng khi phục hồi.

Tài liệu upstream đã đối chiếu với image pin: [Docker builds](https://superset.apache.org/docs/installation/docker-builds/), [REST API](https://superset.apache.org/docs/rest-api/), [dashboard workflow](https://superset.apache.org/user-docs/6.0.0/using-superset/creating-your-first-dashboard/). Image hiện dùng Apache Superset 6.1.0 theo digest trong Dockerfile.
