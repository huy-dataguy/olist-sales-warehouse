# Vận hành SalesDW trên máy cá nhân

UI hiện hành là **Superset**, thay Metabase theo yêu cầu mới. Xem [Superset demo guide](superset-demo-guide.md) để đăng nhập, chạy 5 báo cáo, SQL Lab và bộ phân tích. Các mục Metabase/rotation bên dưới là lịch sử nghiệm thu trước lần chuyển BI; không dùng làm bằng chứng Superset app restore hoặc credential rotation đã đạt.

Phạm vi được cho phép: Compose project `salesdw`; databases `sales_dw`, `airflow_meta`, `metabase_meta`; restore chỉ vào database mới `sales_dw_restore_*`. Migrations đi qua `scripts/migrate.py`, có plan, target guard và checksum. Không dùng reset/drop để chữa lỗi.

## Đăng nhập

| UI | User | File local chứa credential |
|---|---|---|
| Superset :18088 | `demo` | `var/secrets/superset_admin.json` |
| Metabase :13000 | `demo@salesdw.local` | `var/secrets/bi_admin.json` |
| Airflow :18080 | `demo` | `var/airflow-logs/simple_auth_passwords.json` |
| MinIO :19001 | `salesdw_operator` | `var/secrets/minio_root_password` |

Mở file tại máy để lấy mật khẩu. Không paste chúng vào README, screenshot, commit hoặc ticket. `.env`, `var/`, raw ZIP và volumes được bỏ qua khi commit. Source build MinIO và HTTP nội bộ chỉ dùng trong trust boundary local. Admin Metabase dùng account riêng; kết nối dữ liệu của Metabase luôn là role `salesdw_bi` chỉ đọc published exports.

## Startup và source

```bash
make prepare build
docker compose --env-file .env -f infra/compose.yaml up -d --wait postgres minio
make migrate-plan migrate
docker compose --env-file .env -f infra/compose.yaml run --rm airflow-init
docker compose --env-file .env -f infra/compose.yaml run --rm superset-init
make start
make source run verify-bi docs verify-boot verify-runtime
```

`make demo` gom các bước chính trên, không reset tài nguyên có sẵn. Source download được kiểm bằng SHA-256 trong `data/source-manifest.json`; archive sai hash không được đưa vào raw. Nếu Kaggle yêu cầu đăng nhập, tải đúng version vào `data/raw/olist/brazilian-ecommerce-v2.zip` rồi chạy `make source`; đừng sửa checksum để bỏ qua cảnh báo.

Mở dashboard từ `var/bi/superset-state.json`: mỗi URL/dataset pin một release cụ thể. Dashboard không tự cộng distinct theo ngày hay tự định nghĩa AOV. Muốn có assets cho release mới, chạy `make verify-bi`; URL release cũ vẫn đọc bản published được giữ lại.

## Schedule, retry và recovery

DAG `sales_warehouse_pipeline`: 02:00 Asia/Ho_Chi_Minh, catchup=false, max_active_runs=1, LocalExecutor, tối đa 2 retry cách nhau 30 giây, task timeout 15 phút. DAG mới tạo ở trạng thái paused. Bật qua UI hoặc CLI khi muốn chạy theo lịch.

```bash
docker compose --env-file .env -f infra/compose.yaml exec -T airflow-scheduler \
  python /workspace/infra/airflow-entrypoint.py dags unpause sales_warehouse_pipeline

docker compose --env-file .env -f infra/compose.yaml exec -T airflow-scheduler \
  python /workspace/infra/airflow-entrypoint.py dags trigger sales_warehouse_pipeline \
  --run-id demo_retry_01 -c '{"fail_once":"load"}'
```

`fail_once` chỉ gây lỗi lần thử đầu; `fail_at` gây lỗi mọi lần thử. Các giá trị chỉ chọn từ tên stage, không được nội suy trực tiếp vào shell code. Không clear một run đã failed trong ledger để biến nó thành successful. Bắt đầu run mới:

```bash
make resume-run RUN_ID=<uuid-cua-run-co-batch-da-commit>
```

Resume xác minh batch committed và artifact identity; tạo run/receipt mới, không nhân đôi source versions. Khi batch chưa commit, chạy lại `make run` từ raw; source hash và dedup vẫn được kiểm. Context/artifacts nằm ở `var/runs/<uuid>/`; Airflow logs ở `var/airflow-logs/`. Task failure cuối cùng ghi `ops.pipeline_runs.state='failed'`; các task sau là upstream_failed và publication pointer giữ nguyên.

Lease có fencing token và thời hạn 20 phút. Transformation/snapshot/publish kiểm owner/token; checkpoint nằm cùng transaction với model. Nếu tiến trình bị kill, đợi lease hết hạn hoặc điều tra owner; không tự sửa lease trong SQL console. Failed candidate giữ để chẩn đoán. `finish` chỉ thành công sau publication và lặp lại yêu cầu publish để kiểm tra đường phục hồi mất acknowledgement.

Metric export cũng có đường phục hồi mất acknowledgement: nếu 5 exports đã commit nhưng state chưa cập nhật, retry kiểm manifest gốc, hash/query/result, oracle và binding rồi hoàn thành state. Không ghi lại exports hoặc thay manifest của bản đã ghi.

## Mô hình, source cut và semantic

18 dbt models: 7 staging, 1 intermediate, 7 dimensions, 3 facts. Staging/intermediate là bảng vật lý có ANALYZE vì dữ liệu JSONB/distinct cần thống kê tốt. Facts incremental delete+insert theo tập order bị ảnh hưởng; parent được tính lại từ toàn bộ tập child đã chấp nhận. Registry integer SK bền vững qua replay/full refresh.

10 bảng consumer được copy trong transaction repeatable-read dưới một release ID. Constraint, count và logical hash phải đạt trước khi snapshot chuyển trạng thái. MetricFlow chạy trên view yêu cầu session binding `sales_dw.candidate_release_id`; thiếu/sai binding bị từ chối. Mỗi export được kiểm SQL oracle và native CLI CSV, sau đó publish pointer atomically trong PostgreSQL.

Hai compatibility findings đã được chứng minh bằng runtime:

1. dbt-metricflow 0.15.0 đọc `<project>/target/semantic_manifest.json` cố định. Mỗi run có project directory và target riêng, không ghi vào source bind mount read-only.
2. Parser V2 của dbt Core 1.12.6 bỏ mất `fill_nulls_with` trong manifest. Runtime dùng semantic YAML legacy còn hỗ trợ. Tháng có orders nhưng không có items cho merchandise=0; AOV với denominator=0 là NULL. Không sửa chuỗi SQL sinh bởi MetricFlow.

Tài liệu chính thức: [simple metrics](https://docs.getdbt.com/docs/build/simple), [semantic YAML spec](https://docs.getdbt.com/docs/build/latest-metrics-spec). Behavior thực tế được pin theo dependency lock và kiểm lại khi upgrade.

`make docs` tạo catalog/lineage thật và static HTML tại http://localhost:18081/static_index.html. Đây là tài liệu của mutable working models; consumer release/MetricFlow lineage còn có ở `ops.snapshot_relations`, `ops.lineage_edges`, `ops.export_queries` và run artifacts.

## Backup và restore

```bash
make backup
make verify-restore
```

Backup: consistent `sales_dw` dump bằng role backup; application database dumps riêng; raw ZIP; checksums/migrations/image IDs trong manifest. Folder `var/backups/<timestamp>/` private, không được commit. File chưa mã hóa và vẫn trên cùng máy: phục hồi lỗi logic, không chứng minh host-loss RPO.

Restore drill luôn tạo target mới và từ chối target đã tồn tại. `pg_restore --single-transaction --exit-on-error`; sau restore, vô hiệu hóa lease và đánh dấu inflight runs abandoned/failed trong target mới. So sánh SK registry hash, 10 snapshot manifests, KPI, counts, pointer và trạng thái live trước/sau. Restore app database dumps sang dịch vụ riêng chưa được nghiệm thu; có thể tái tạo dashboards/DAG từ code nhưng đó không thay thế bằng chứng app restore.

Chạy kiểm tra trên target vừa restore:

```bash
docker compose --env-file .env -f infra/compose.yaml run --rm \
  -e SALES_DW_DATABASE=sales_dw_restore_<timestamp> --entrypoint python worker \
  /workspace/scripts/verify_runtime.py all
```

`verify_faults.py` cũng chỉ chấp nhận target restore; nó ghi rõ synthetic fixtures vào raw/audit, kiểm rejection/fencing/SCD2 và không đổi published source data. Target đó là sandbox kiểm thử sau khi drill hoàn tất, không tiếp tục dùng như bản backup nguyên trạng.

## Incremental integration test

Tạo một target mới, rồi chạy:

```bash
docker compose --env-file .env -f infra/compose.yaml run --rm migrate \
  --apply --approved-project salesdw --restore-target sales_dw_restore_incremental_<timestamp> --initialize-empty
docker compose --env-file .env -f infra/compose.yaml run --rm \
  -e SALES_DW_DATABASE=sales_dw_restore_incremental_<timestamp> --entrypoint python worker \
  /workspace/scripts/verify_incremental.py
```

Test dùng hai tháng thật, giữ lại một payment rồi giao muộn trong kế hoạch mô phỏng, replay cùng batch và full refresh. Payload không đổi; delivery sequence là simulated. Test yêu cầu database rỗng; không có reset tự động. Không đưa target/số liệu synthetic vào demo baseline Olist.

Test còn giữ lại một product master đang được item tham chiếu, rồi giao master ở batch sau: inferred member được bổ sung thuộc tính nhưng giữ integer SK. Các build-only fixture không được ghi succeeded vì không đi qua publication; audit ghi rõ `isolated_build_only_fixture`.

Trên target đã restore (không dùng live database):

```bash
make verify-faults RESTORE_DB=sales_dw_restore_<timestamp>
make verify-recovery RESTORE_DB=sales_dw_restore_<timestamp>
make verify-correction RESTORE_DB=sales_dw_restore_<timestamp>
make verify-publish-ack RESTORE_DB=sales_dw_restore_<timestamp>
```

Recovery kiểm lỗi sau load commit, giữa snapshot, giữa exports, parity mismatch và sau semantic commit. Correction thêm **revision tổng hợp có provenance riêng** cho một đơn đã giao, kiểm phân loại lại order/items/metrics ở release mới, bản cũ không đổi, sau đó rollback pointer trong sandbox. Đây không phải khả năng CDC của nguồn Olist thật. Sau correction, accepted source cut trong sandbox đã thay đổi; hãy dùng target mới nếu cần lại baseline nguyên trạng.

`verify-publish-ack` cần ít nhất hai retained published releases: giữ lease bằng owner mới, rồi gửi lại acknowledgement của release khác với pointer hiện hành. ACK không đổi pointer, không tạo publication event trùng và không giải phóng lease của owner mới.

## Rollback release đã công bố

Không sửa fact hay reset checkpoint. Chỉ chuyển pointer về một release đã published, còn đủ metadata/exports, dưới lease và kiểm `expected-current`. Mỗi lần có audit event/reason. Thực hiện plan trước; áp dụng trên live là quyết định vận hành cần được người sở hữu chấp thuận:

```bash
docker compose --env-file .env -f infra/compose.yaml run --rm --entrypoint python worker \
  /workspace/scripts/rollback_release.py --target-release <retained-uuid> --expected-current <current-uuid>
# Sau khi review plan/ảnh hưởng, lặp lại với:
# --apply --approved-database sales_dw --reason "Incident ...; approved recovery ..."
```

URL Metabase cũ vẫn pin release cũ; `make verify-bi` chọn lại mặc định theo pointer sau rollback. Drill chỉ chuyển pointer của database restore; không rollback live để làm demo. Đây là logical release rollback, không hoàn tác một schema migration.

## Capacity, logs và security

`make capacity` ghi Docker inventory (bao gồm cả tài nguyên ngoài dự án để có upper bound bảo thủ), dung lượng artifacts và container memory. Trước raw/snapshot, pipeline chặn nếu free disk dưới 5 GB hoặc estimate cộng dư địa candidate tới 90% ngân sách 70 GB. Docker logs được xoay 3 file × 10 MB/service. Host Airflow/dbt artifacts có inventory; chưa bật auto-delete. Không chạy Docker system prune.

Role BI không đọc landing/work/warehouse_store hoặc ghi exports. Role ingest không update nguồn đã nhận; publisher không ghi facts. Worker không mount bootstrap credential. Airflow cần các credential pipeline theo stage trong local trusted boundary; chưa triển khai external secret manager hoặc per-task OS isolation.

Controlled BI rotation:

```bash
docker compose --env-file .env -f infra/compose.yaml run --rm migrate --rotate-role bi
docker compose --env-file .env -f infra/compose.yaml run --rm migrate --apply --approved-project salesdw --rotate-role bi
docker compose --env-file .env -f infra/compose.yaml up -d --force-recreate airflow-api airflow-scheduler airflow-dag-processor
make verify-bi verify-security
```

Thực hiện khi pipeline idle. Entrypoint đổi password, kiểm credential cũ bị từ chối/credential mới hoạt động, cập nhật Metabase và secret files; lỗi sẽ cố gắng rollback. Recreate để remount file secret đã atomic-replace. Rotation proof không bao gồm toàn bộ account/operator credential.

## Browser, CI và bằng chứng chia sẻ

`make verify-browser` dùng Chrome sẵn có, `SALES_DW_BROWSER=/path/to/chrome`, hoặc Chromium của Playwright. Trên máy chưa có browser, cài qua `uv run --no-project --with playwright python -m playwright install chromium`. Không commit file đăng nhập.

`make package-evidence` kiểm release của Warehouse và browser trùng nhau, xuất 5 CSV aggregate cùng ảnh chụp thật và reports có allowlist vào `docs/evidence/runtime/`/`output/reports/`. Không copy raw hoặc credential. Dữ liệu aggregate vẫn phải giữ attribution/license Olist; không chia sẻ như dữ liệu độc quyền của Abbott.

Workflow `.github/workflows/ci.yml` pin actions theo commit, chạy contracts/tests khi PR/push và cho phép full Docker integration thủ công trên runner tạm. Workflow mới được viết và kiểm cú pháp local; chưa có remote PR/run để gọi là CI acceptance. Git repository/remote chưa được khởi tạo hay push thay bạn.

## Khi có sự cố

Đầu tiên giữ release đã công bố, đọc stage log và DQ diagnostic. Schema/checksum/revision conflict cần sửa source contract hoặc nguồn; không retry vô hạn. SQL/parity failure cần đối chiếu candidate và query artifacts; không publish thủ công bằng UPDATE. Nếu thiếu disk, dừng optional backfill, xem inventory và kế hoạch giữ raw/release/backup. Nếu mất cả host, các backup local không đủ; off-host encrypted replication là bước triển khai riêng.
