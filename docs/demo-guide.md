# Kịch bản trình diễn 7–10 phút

1. Mở [Superset Sales Overview](http://localhost:18088/superset/dashboard/olist-sales-87f01740/): bắt đầu từ câu hỏi và “Dùng để”, rồi bảng **Nhận xét & câu trả lời**, không chỉ đọc số trên cards. Nguồn Olist, một publisher với bảy feed. Tháng 2018-07: delivered value 867.953,46 theo quy ước BRL, 6.159 delivered orders, 6.100 distinct delivered customers, AOV 140,92; MoM +1,39%. Nêu hướng kiểm tra cơ cấu/độ đầy đủ kỳ, chưa quy nguyên nhân tăng. Đổi tháng rồi Apply filters; cả nhận xét và KPI đổi, full-period trend vẫn giữ ngữ cảnh.
2. Mở sơ đồ bus/ERD trong `docs/visuals/`: ba process grains, bảy conformed dimensions, integer SK registry. Cho ví dụ một khách hàng có nhiều customer_id theo đơn; địa chỉ theo đơn được giữ riêng.
3. Mở dbt docs :18081: nguồn accepted versions → staging → intermediate → dimensions/facts. Facts payments/items không được join atomic để tổng hợp tiền; semantic layer drill-across qua time/geography.
4. Mở Airflow :18080: run `acceptance_retry_fixed_20261015`, bước load có 2 attempts và DAG success. Đối chiếu `acceptance_failure_20261015`: raw thất bại sau 3 attempts, downstream upstream_failed; release cũ vẫn truy vấn được.
5. Mở Customer Behavior: đọc nhận xét 3,00% khách có ít nhất 2 delivered orders, đóng góp 5,51% observed merchandise. Giải thích cohort denominator, future cells, cutoff và vì sao không gọi khách một đơn là churn. Mở Products/Sellers và Delivery/Payments để chỉ ra câu hỏi, câu trả lời và hướng phân tích tiếp của từng trang. Kết thúc bằng “Cách đọc”/“Giới hạn kết luận” để tách quan sát khỏi giả thuyết.
6. Mở `output/analysis/business-analysis.md`, notebook và một Saved query trong SQL Lab. Cho xem định nghĩa, số liệu và giới hạn kết luận. Nếu người phỏng vấn muốn đi sâu kỹ thuật, mở `incremental.json`: late payment recomputes parent, replay không thêm business versions, full/incremental tương đương và SK ổn định.
7. Mở `var/evidence/restore.json` và `faults.json`: restore cô lập 102 giây ở lần đo đầu, registry/KPI/pointer khớp; schema/status/conflicting duplicate bị cách ly; SCD2 overlap bị PostgreSQL từ chối. Chỉ rõ đây là fixture mô phỏng, không phải lịch sử thật của Olist.

Các giá trị mô tả phải được kiểm lại từ artifacts nếu chạy nguồn/model mới. Số liệu hiệu năng là đo trên host local này, không suy rộng sang SLA doanh nghiệp.

Nếu cần đi sâu: mở `correction.json` để thấy sửa một order cũ làm metric giảm đúng 58,90 ở release mới, old release vẫn nguyên và rollback pointer có audit. Mở `pipeline-recovery.json` để thấy lỗi sau semantic commit được retry an toàn. Cả hai chỉ chạy trên target restore, không sửa số liệu demo nguồn thật.

Khi không chạy Docker trong buổi phỏng vấn, dùng `docs/evidence/superset/screenshots/`, báo cáo/notebook/CSV ở `output/analysis/` và các metric exports ở `output/reports/`. Bộ sơ đồ/PDF cũ là baseline trước ADR-014 nên nhãn Metabase trên đó đã được supersede; không trình bày nó như UI hiện hành.

Một cách giới thiệu bằng tiếng Anh:

> I built a local Kimball warehouse using real Olist data, with Airflow orchestration, dbt transformations and executable MetricFlow metrics. Each published release contains a consistent warehouse snapshot and validated metric exports. I verified replay safety, late-child recomputation, failure isolation, least-privilege access and an isolated backup restore. The project is an independent portfolio implementation, not a representation of an employer's internal architecture.

Giới hạn cần nói đúng: single host, không HA, chưa có encrypted off-host backup, Olist là static snapshot, lịch sử hiệu lực SCD2 nằm trong fixture riêng, remote CI chưa có bằng chứng chạy và toàn bộ 22 operational scenarios chưa được nghiệm thu đầy đủ.
