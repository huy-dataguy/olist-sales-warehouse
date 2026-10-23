# Runtime implementation and bounded acceptance — 2026-10-16

Đã có hệ thống local chạy thật với Olist → MinIO → PostgreSQL → dbt → MetricFlow → **Superset**, do Airflow điều phối. Người dùng chốt dừng ở mức demo và chuyển BI từ Metabase sang Superset. Đây là portfolio trên một máy, **không phải chứng nhận production-ready/HA** hay mô tả kiến trúc nội bộ Abbott/Concentrix.

## BI revision — Superset

Một Tổng quan kinh doanh dẫn tới 5 report pages chuyên sâu; 60 đối tượng đang sử dụng (48 KPI/biểu đồ + 6 bảng điểm nhấn + 6 menu điều hướng); 8 saved analysis queries chạy trong SQL Lab. Published order/payment/customer/cohort views bổ sung qua migration 005 trước đây, không có migration mới cho trang tổng quan. Core metrics vẫn từ MetricFlow. Mỗi trang chỉ có ngữ cảnh ngắn, KPI, điểm nhấn và biểu đồ; hướng dẫn/giới hạn đầy đủ chuyển vào mô tả biểu đồ/tài liệu theo ADR-016. Nhận xét theo tháng đổi cùng native filter ở bốn trang; customer/trust giữ cutoff/producer riêng. [Hướng dẫn báo cáo](superset-demo-guide.md), [bộ phân tích](../output/analysis/business-analysis.md) và [manifest BI](evidence/superset/manifest.json) là handoff hiện hành. Metadata Superset được cô lập; metadata Metabase cũ được giữ lại.

Actual API/browser checks bao gồm chọn tháng, đối soát KPI, phát hiện render errors và chụp sáu trang. Lỗi visualMap của heatmap đã được sửa bằng legend continuous; SavedQuery cần created_by đúng user để xuất hiện/chạy được qua API. Đây là lý do phải kiểm giao diện và SQL Lab thật, ngoài việc query trả HTTP 200.

## Executive overview và điều hướng — 2026-10-16

### Giao diện nghiệp vụ rút gọn — ADR-016

Theo phản hồi tiếp theo, đã bỏ các panel lặp `Dùng để`, `Cách đọc & phân tích sâu`, `Giới hạn kết luận` khỏi cả sáu trang. Tiêu đề nghiệp vụ, một dòng ngữ cảnh, menu nút và KPI được ưu tiên; cuối trang chỉ có một ghi chú nguồn/định nghĩa ngắn. Release/source-cut và provenance vẫn ở trang Chất lượng dữ liệu, không lặp trên các trang kinh doanh. Full guides được giữ trong mô tả biểu đồ và tài liệu. Follow-up phiên bản 3 dùng hành động nghiệp vụ ngắn, không hướng người dùng business sang SQL Lab. Công thức, tử/mẫu, dữ liệu và published release không đổi.

- `make test`: exit 0, **28 tests** đạt; `make refresh-bi`: exit 0, **60 chart queries + 8 SQL Lab queries**, numeric parity, sáu mô tả có full methodology và hai lần bootstrap không tạo trùng.
- `make verify-browser`: exit 0, **6 trang** không còn panel bị phản đối; **8 KPI** tổng quan vừa màn hình đầu ở **1720/1366**; ba nhận xét/trang, month changes, fixed scopes và **14 lượt bấm** điều hướng đều đạt.
- `make verify-design`: 137 source/fixture/DDL contracts + 5 semantic cases đạt trong lượt này; `make verify-spec` giữ 20 REQ/TASK/V identifiers. Không diễn giải các check UI này thành chạy lại ingestion/Airflow/restore.
- Menu dùng virtual dataset v2, wording nhận xét dùng v3; các định nghĩa cũ được giữ. Không có migration DWH hoặc nguồn dữ liệu mới.

Ghi chú kỹ thuật cho lần sửa sau: sticky-table của Superset 6.1 cần THEAD có chiều cao khác 0 để đo cột. `display:none` khiến API vẫn thành công nhưng menu nằm trong sizer ẩn; giữ một hàng đo 1px không nhìn thấy, rồi kiểm liên kết thật trên trình duyệt. Không thay bài kiểm UI bằng HTTP 200.

[Mở điểm vào](http://localhost:18088/superset/dashboard/olist-overview-87f01740/). Chọn mô hình tổng quan → chuyên sâu thay vì một trang chứa mọi chart. Trang chính có 8 KPI, 4 biểu đồ xu hướng/đóng góp, ba nhận xét có đối soát SQL và menu tới năm trang con. Trên mọi trang đều có đường về tổng quan và chuyển ngang. Không tạo target/SLA, profit hoặc kết luận nhân quả không có dữ liệu.

- `make refresh-bi`: exit 0; bootstrap hai lần giữ IDs/counts, 60 chart queries và 8 SQL Lab queries thành công; nhận xét overview/sales kiểm cả kỳ thiếu mẫu số/so sánh, tháng 06/07 được kiểm độc lập. Giữ release handoff, không resolve sang publication khác cho thay đổi UI.
- `make verify-browser`: exit 0; đủ sáu trang, native month change trên overview/sales/commercial/service; 14 lượt bấm thật overview↔năm trang con và chuyển ngang, cùng month/release. Customer/trust chỉ lọc menu theo tháng, các nhận xét nghiệp vụ giữ nguyên cutoff/producer.
- Ảnh baseline tháng 07/2018 và ảnh điều hướng tháng 06/2018 ở 1720/1366 px được kiểm. Câu hỏi, findings và follow-up đều vừa chiều ngang; không chỉ kiểm page overflow.
- `make test`: 26 tests đạt. `make verify-design`: 137 source/fixture/DDL contract checks và 5 offline semantic cases đạt; `make verify-spec` xác nhận 20 REQ/TASK/V references ổn định. Đây không phải lần chạy lại toàn bộ ingestion/Airflow/restore hoặc production acceptance.
- Đang sử dụng 60 chart objects. Metadata lịch sử vẫn giữ nên inventory vật lý của release prefix có thể nhiều hơn số đang gắn vào sáu dashboard; không xóa legacy assets để làm count đẹp.

Bài học vận hành UI: query response, filter UI và DOM cập nhật bất đồng bộ; chờ cả ba khớp trước khi kiểm/bấm tiếp. Chụp grid đã hiển thị thay vì frame đang rehydrate sau reset filter. Bảng có thể bị cắt bên trong dù page không tràn; gate kiểm cả cột câu hỏi/nhận xét/hành động ở hai độ rộng. Những điều này được ghi lại trong analytics design để giữ hành vi khi sửa sau.

`acceptance_superset_pin_20261015` đã publish một release mới trong lúc trình duyệt giữ dashboard handoff. Reload vẫn trả dữ liệu/SQL của release đã pin cho 10 sales charts ban đầu; bằng chứng nằm trong `superset-publish-transition.json`. Đây là một lần chạy thật, không đổi pointer bằng SQL để mô phỏng. Bảng nhận xét được thêm sau drill này, có SQL/API/filter checks riêng, không kế thừa claim concurrent-publication chưa chạy lại. Notebook đã thực thi 9 code cells thành công; kernel chỉ đọc các CSV đã đối soát, không dùng secret database.

## Kết quả hiện tại

| Thành phần | Kết quả thực thi |
|---|---|
| Nguồn | 7 feed, 451.535 dòng; ZIP 44.717.580 bytes; SHA-256 khớp manifest |
| Warehouse | 7 dimensions, 3 facts; orders 99.441, items 112.650, payments 103.886 |
| Kimball | Integer SK registry, conformed dimensions, role-playing dates, PK/FK/grain constraints, unknown/inferred members |
| dbt | 18 models + 75 tests = 93 nodes đạt trong lần build mới nhất |
| Semantic | MetricFlow native CLI + generated SQL + independent SQL oracle; 5 exports đạt parity |
| BI | Superset: overview + 5 trang con, 60 active chart objects; SQL-backed findings, native month filter bốn trang, 14 actual navigation clicks, fixed scopes, hai viewport, metadata idempotency và SQL Lab |
| Airflow | `acceptance_handoff_20261015` success, khoảng 264 giây; retry và terminal failure đã kiểm riêng |
| Restore | DWH restore vào target mới trong 102,056 giây; keys/KPI/ACL/pointer khớp, live không bị ghi đè |
| Capacity | Đã đo inventory dưới 70 GB; báo cáo có thời điểm đo và phương pháp cộng bảo thủ |

BI handoff pin release `87f01740-0523-5fd4-be0e-eb52acb2842a`, producer `5ac008ff-3041-54cf-b03a-b7e76a5fa82f`, source cut 1. Publication mới có thể tồn tại song song; UI không tự thay dữ liệu đã pin. `var/bi/superset-state.json` ghi assets/URLs hiện hành. [Manifest runtime trước chuyển BI](evidence/runtime/manifest.json) giữ bằng chứng lịch sử; không được đổi nhãn Metabase thành Superset để kế thừa bằng chứng sai.

Toàn nguồn: delivered orders **96.478**, distinct delivered customers **93.358**, delivered merchandise value **13.221.498,11** theo quy ước BRL, chưa gồm freight. Không gọi đây là profit/net revenue, không suy ra refunds hay currency từ CSV không có các trường đó.

## Coverage so với thiết kế

“Đã kiểm” dưới đây luôn là scope cụ thể; không đánh đồng với nghiệm thu toàn bộ mọi tiêu chí của V-*.

| Hợp đồng | Bằng chứng chạy thật / ranh giới |
|---|---|
| V-001, V-002 — source/raw | Archive checksum, 7-feed validation, S3 PUT/GET, source-loss fallback, corrupt payload rejection; `runtime-sales_dw.json`, `faults.json` |
| V-003, V-007 — admission/quality | Schema/status/conflicting duplicates/equal revision bị quarantine; rejected receipt; source cut/pointer giữ nguyên; occurrence accounting và source warnings; `faults.json` |
| V-004, V-013 — Warehouse/Kimball | 93 dbt nodes, ten snapshot relations, money/count/FK/grain/hash/lineage checks; runtime report và per-run dbt/snapshot artifacts |
| V-005 — semantics | 8 metrics, 5 exports, native adapter parity, zero denominator NULL, exact money, illegal product grouping rejected; per-run `semantic.json` và runtime report |
| V-006 — BI | Superset: 60 chart queries, nhận xét có parity với SQL/arithmetic, 8 saved-query executions, 6 browser pages, nhận xét đổi cùng tháng ở bốn trang, 14 real navigation clicks, fixed customer/trust scopes, hai viewport và metadata idempotency; `superset.json`, `superset-browser.json`, `analytics.json`. Metabase proof cũ được giữ riêng |
| V-008 — orchestration | Actual DAG success; load try=2 sau lỗi đầu; raw fail sau 3 attempts, downstream upstream_failed, ledger failed; `airflow.json` |
| V-009 — replay/correction | Hai tháng thật, late payment recomputes parent, replay 0 new versions, full/incremental hashes giống, SK ổn định; `incremental.json`. Synthetic old-order correction restates order/items/metrics và giữ release cũ; `correction.json` |
| V-010 — recovery | Load commit sống qua lỗi build; snapshot rollback; export/parity chặn publish; semantic commit acknowledgement recovery; publish acknowledgement idempotent; `pipeline-recovery.json` |
| V-011 — SQL performance | EXPLAIN ANALYZE/BUFFERS, 3 warm trials/filter, cùng kết quả; 20 BI-query samples; runtime report. Không suy rộng thành SLA doanh nghiệp |
| V-012 — reproducibility | Docker services, full source pipeline và UI chạy trên host hiện tại; chưa clean-room clone trên máy thứ hai |
| V-014 — effectivity | Inferred product → enriched giữ SK; SCD2 late split/as-of và PostgreSQL overlap rejection trên fixture cô lập. Không có lịch sử Type 2 thật từ Olist |
| V-015 — security | Actual SQL/S3 denials, BI readonly, bootstrap secret không mount worker, loopback ports; BI rotation/remount; `rotation.json`, runtime/health reports. Không phải pentest/CVE certification |
| V-016 — restore/rollback | Isolated DWH restore timed + signatures; fenced rollback pointer và stale-plan rejection trong sandbox. App DB dump có, app restore chưa kiểm |
| V-017 — publication isolation | Fixed-cut snapshots, required binding, partial export blocked, stale owner rejected, concurrent lease one winner, browser pinning |
| V-018 — source cuts | Serialized committed batches, models/checkpoints cùng cut, late-child/correction; không có source CDC hay claim mọi concurrency interleaving đã thử |
| V-019 — CI | Workflow được viết, actions pin commit, lock/compile/contracts/tests chạy local. Chưa có remote GitHub PR/run, branch protection hay release approval evidence |
| V-020 — operations | Health/logs/query/resource/restore measurements, capacity boundary unit tests, runbook. Retention inventory-only; alert routing, long-duration SLO và encrypted off-host recovery chưa hoàn tất |

## Tình huống khó đã tái hiện

- Replay nguyên batch: **0 new source versions**, receipt audit tăng, SK/metrics không đổi.
- Product master giao trễ: fact dùng inferred SK; master tới bổ sung thuộc tính mà giữ SK.
- Payment giao trễ: order parent được tính lại từ toàn bộ child set.
- Revision trạng thái đơn mô phỏng: delivered giảm 1, canceled tăng 1, giá trị giảm đúng 58,90; item cùng order đổi classification. Bản trước không đổi.
- Lỗi giữa snapshot/exports: không lưu nửa bộ dimension/fact hoặc báo cáo.
- Metric đã commit nhưng mất acknowledgement: retry xác minh nội dung đã lưu và hoàn tất state, không duplicate. Publication acknowledgement đến sau lease takeover vẫn thành công, giữ nguyên lease mới và pointer (`ack-recovery.json`).
- Two-owner race: một lease winner; token cũ bị PostgreSQL từ chối sau takeover.
- Browser pin bản cũ khi pointer đổi: mọi business card vẫn dùng cùng bản cũ.
- SCD2 fixture có valid time rõ ràng: late interval split, biên half-open, physical overlap rejection.

Synthetic fixtures chỉ nằm trong restore targets, raw prefix `simulated/`, artifact/revision provenance ghi rõ. Không trộn fixture vào `sales_dw` hoặc kết quả kinh doanh nguồn thật.

## Quyết định triển khai

- dbt/MetricFlow có virtualenv riêng với Airflow; images/dependencies được pin.
- Staging/intermediate materialize table + ANALYZE để planner có thống kê; chỉ đổi physical design, không đổi grain.
- MetricFlow 0.15 CLI cần per-run project/target. dbt Core 1.12 V2 parser làm mất `fill_nulls_with`; dùng legacy semantic YAML còn hỗ trợ, không rewrite generated SQL.
- Snapshot/export là immutable consumer releases; BI không truy cập mutable work.
- Finish bắt buộc publication đã commit. Build-only fixture có audit riêng, không giả thành successful full pipeline.
- Secret atomic replace cần remount long-lived containers; BI rotation đã kiểm credential cũ/new và Metabase.

## Chưa nghiệm thu / không được tuyên bố

1. Single-host, không HA/DR site/host-loss RPO. Backup local private nhưng chưa encrypted/off-host.
2. App database restore vào stack độc lập; hiện chỉ DWH restore thật và app dumps.
3. Remote CI/release governance, clean-room máy khác, dependency vulnerability scan và pentest.
4. Automated retention có dependency safety, external alert receiver/on-call và SLO soak test. Không tự xóa raw/old releases/fixture databases/Docker cache.
5. Generic CDC/SCD2 business-history connector: Olist không cung cấp lịch sử đó; fixture không thay thế source contract.
6. Native DSH dossier admission chưa thực hiện; không tạo `dossier.json` để suy diễn “all gates passed”.

Failed/debug runs ban đầu được giữ để chẩn đoán. Services chạy trên loopback. Restore databases giữ lại để đối chiếu, được tính trong capacity inventory.
