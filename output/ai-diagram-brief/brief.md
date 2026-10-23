SalesDW Diagram Generation Brief

Thông tin để AI tạo hình kiến trúc và ERD theo ảnh mẫu

Bản 2026-10-19. Đây là brief cho hai ảnh kỹ thuật, không phải bản báo cáo dự án trước đó. Ảnh mẫu chỉ là tham chiếu phong cách; tên bảng, công nghệ và đường nối phải lấy từ tài liệu này.

Cách dùng

1. Tải PDF này cùng hai ảnh mẫu lên công cụ AI bạn chọn.
2. Yêu cầu tạo hình kiến trúc trước bằng Architecture prompt ở trang 2.
3. Tạo ERD riêng bằng ERD prompt ở trang 3.
4. Nếu công cụ nhận file, đính kèm schema-reference.json hoặc warehouse-full-schema.mmd để giữ đúng tên cột và quan hệ.
5. Dùng Review prompt ở trang cuối để kiểm trước khi xuất.

Sự thật phải giữ nguyên

| Hạng mục | Nội dung |
| Tên dự án | Sales and Customer Analytics Warehouse |
| Phạm vi | Portfolio độc lập; Olist công khai; Docker local; không phải kiến trúc nội bộ Abbott/Concentrix |
| Stack có thật | Python, MinIO, PostgreSQL, dbt Core, local MetricFlow, Apache Airflow, Apache Superset |
| Nguồn | Olist v2 snapshot: 7 CSV feeds, 451.535 dòng, 99.441 orders |
| DWH | Kimball: 7 dimensions + 3 facts; integer dimension SK; conformed dimensions |
| Đầu ra | 8 KPI lõi, 5 MetricFlow exports, 6 dashboard, SQL/notebook |
| Không có trong v1 | OLTP riêng, CDC, streaming, Kafka/Spark/Trino/Iceberg/Delta, telesales, HA |

File không chứa mật khẩu, connection strings, raw data hoặc thông tin nội bộ. PDF là nguồn thông tin; chất lượng chữ và quan hệ trong ảnh do AI sinh vẫn cần kiểm lại. Đối với ERD dày chữ, ưu tiên SVG/diagram code chỉnh sửa được thay vì chỉ một ảnh raster.


---

1 Architecture prompt

Copy nguyên phần tiếng Anh dưới đây; kèm ảnh mẫu kiến trúc.

Create ONE presentation-quality technical architecture diagram using the attached architecture image as a STYLE reference only. Use the attached SalesDW brief as the factual source. Title: Sales and Customer Analytics Warehouse. Subtitle: Olist public data | Local Docker demo. Do not call it an Abbott production system or a streaming lakehouse.

Use a white background, thin dark-gray rounded container borders, tidy orthogonal arrows, generous whitespace and legible sans-serif labels. Include recognizable technology logos for Docker, Apache Airflow, Python, MinIO, PostgreSQL, dbt and Apache Superset only when they can be reproduced accurately; otherwise use clear text labels. MetricFlow is a named semantic engine, not an invented logo. No 3D, decorative illustration, long paragraphs or dashboard-style KPI cards. Export a crisp 4096 x 2304 image, preferably with editable SVG or diagram source.

Draw one outer Docker Compose project salesdw boundary. Place a horizontal Apache Airflow orchestration bar across the top inside it. It schedules a batch DAG and invokes Python/dbt/MetricFlow/publishing tasks; it does NOT carry source rows. Use dashed lines for orchestration and a legend distinguishing them from solid data-flow arrows.

Place the external Olist v2 CSV snapshot source on the left. Inside Docker, arrange the business path left to right: Python ingestion and validation; MinIO immutable raw; PostgreSQL analytical warehouse; semantic and published serving; Apache Superset. The source archive is preserved in MinIO before admission. Python reads validated source records and commits accepted versions into PostgreSQL landing. Make both raw preservation and the later raw replay path understandable, without implying MinIO transforms data.

Inside ONE PostgreSQL service, show the sales_dw business Warehouse database with logical schema compartments: landing, work, warehouse_store, semantic_input, reporting and a smaller ops/audit area. dbt Core transforms landing into mutable work staging/intermediate/dimensions/facts. A controlled snapshot step freezes seven dimensions and three facts into warehouse_store. These are schemas within one Warehouse database, not separate PostgreSQL servers or multiple DWHs. Application metadata databases may be omitted from this business-flow view. Show dbt and MetricFlow as execution tools, not additional storage engines.

Show two governed serving paths: release-bound semantic_input views to local MetricFlow execution to five reporting metric tables; and published Kimball snapshots to governed reporting.analytic_* SQL views for customer/cohort/delivery/payment analysis. Both serve Superset using published-only readonly views. There is no native Superset-to-MetricFlow API connector. A publication gate validates snapshot/exports/SQL parity and atomically publishes a release; failed candidates remain invisible to business consumers. Dashboard assets pin one published release; their metadata handoff is separate from the DAG.

Use short labels. Add a small footer: Independent portfolio | Olist data | Not internal Abbott or Concentrix architecture. Do not add MongoDB, Kafka, Spark, Trino, Iceberg, Delta Lake, Snowflake, ClickHouse, Dagster, Metabase, an LLM, a source OLTP database, CDC, streaming or HA. Do not silently change arrow meanings to make the picture symmetrical.


---

2 ERD prompt

Copy nguyên phần tiếng Anh dưới đây; kèm ảnh mẫu database schema. Các trang sau cung cấp cột và quan hệ chính xác.

Create ONE precise physical/logical Warehouse ERD in the visual style of the attached database-model image: database table cards, blue-gray headers, white rows, exact column names and PostgreSQL data types, PK/FK markers and thin orthogonal crow's-foot relationships. Use the attached SalesDW schema appendix as authoritative data. Title: SalesDW Kimball Warehouse Schema. Do not produce a card infographic or copy the Reddit tables from the reference. Export at least 6000 x 4000 pixels, ideally editable SVG or diagram source. All labels must remain readable when enlarged.

Include exactly TEN Warehouse tables: dim_customer, dim_product, dim_seller, dim_buyer_geography, dim_date, dim_order_status, dim_payment_method, fct_orders, fct_order_items and fct_payments. Display the three fact cards as the visual anchors and place each dimension close to its referring fact fields. Four shared dimensions, dim_customer, dim_buyer_geography, dim_order_status and dim_date, must be conformed physical tables, not three independent copies. Route each relation to the actual PK and FK rows; do not replace relationships with a shared bus line or connect fact tables together.

All PKs and dimensional FKs include release_id. Dimension SKs are bigint, except dim_date.date_key integer YYYYMMDD. Fact identity columns order_key, order_item_key and payment_key are TEXT, not bigint. Each fact also has an independent unique business grain. Copy column names, types and nullability exactly from the appendix; numeric(18,2) money must not become FLOAT. Technical audit columns may be collapsed into an explicitly labeled common metadata footer, never silently invented or removed from the actual model.

Draw the NINETEEN FK roles in the relationship appendix, using one-to-many from each dimension to each fact. fct_orders has customer, buyer geography, order status and FIVE separate dim_date roles: purchase, approved, carrier, delivered and estimated. fct_order_items has customer, geography, status, purchase date, product and seller. fct_payments has customer, geography, status, purchase-date context and payment method. Preserve all roles. State in a small legend that each connector represents the composite release_id plus role key. Audit/release/source tables outside these ten core tables are omitted from this analytical ERD and their external FKs are not reclassified as dimension relationships.

Add compact fact-grain notes: orders = source_system + order_id, accumulating snapshot; items = source_system + order_id + order_item_id, transaction; payments = source_system + order_id + payment_sequential, transaction. order_id is a degenerate dimension, not a reason to create a fact-to-fact FK. Do not infer a payment-to-product allocation. Payment purchase date is order context, not a payment event timestamp.

Do not add customer or product names, demographics, telesales, campaign, vendor or clinical tables. The real Olist snapshot does not provide genuine historical SCD2; product valid-time fields are a capability tested separately with labeled fixtures. Do not fabricate SCD2 history. If full metadata makes one poster crowded, create a clearly labeled readable business-column ERD and retain the complete schema in an appendix. Do not generate extra relationships or substitute incorrect text for illegible labels.


---

3 Dimension columns phần một

Các bảng đều thuộc warehouse_store. PK là composite gồm release_id và key. NN = NOT NULL. Audit columns chung được gom ở trang kế; JSON/Mermaid giữ toàn bộ cột.

dim_customer

| Column | PostgreSQL type | Key | Null |
| release_id | uuid | PK | NN |
| customer_key | bigint | PK | NN |
| source_system | text | - | NN |
| customer_unique_id | text | - | nullable |
| is_inferred | boolean | - | NN |

dim_product

| Column | PostgreSQL type | Key | Null |
| release_id | uuid | PK | NN |
| product_key | bigint | PK | NN |
| source_system | text | - | NN |
| product_id | text | - | nullable |
| version_identity | text | - | NN |
| category_source | text | - | nullable |
| category_english | text | - | nullable |
| category | text | - | NN |
| category_missing | boolean | - | NN |
| valid_from | timestamp without time zone | - | nullable |
| valid_to | timestamp without time zone | - | nullable |
| is_current | boolean | - | NN |
| business_effectivity_known | boolean | - | NN |
| is_inferred | boolean | - | NN |

dim_seller

| Column | PostgreSQL type | Key | Null |
| release_id | uuid | PK | NN |
| seller_key | bigint | PK | NN |
| source_system | text | - | NN |
| seller_id | text | - | nullable |
| seller_city | text | - | nullable |
| seller_state | text | - | nullable |
| seller_zip_code_prefix | text | - | nullable |
| is_inferred | boolean | - | NN |


---

4 Dimension columns và metadata chung

dim_buyer_geography

| Column | PostgreSQL type | Key | Null |
| release_id | uuid | PK | NN |
| buyer_geography_key | bigint | PK | NN |
| source_system | text | - | NN |
| postal_prefix | text | - | nullable |
| city | text | - | nullable |
| state | text | - | nullable |

dim_date

| Column | PostgreSQL type | Key | Null |
| release_id | uuid | PK | NN |
| date_key | integer | PK | NN |
| source_system | text | - | NN |
| full_date | date | - | nullable |
| month_start | date | - | nullable |
| day | smallint | - | nullable |
| month | smallint | - | nullable |
| quarter | smallint | - | nullable |
| year | smallint | - | nullable |
| weekday | smallint | - | nullable |

dim_order_status

| Column | PostgreSQL type | Key | Null |
| release_id | uuid | PK | NN |
| order_status_key | bigint | PK | NN |
| source_system | text | - | NN |
| status_code | text | - | nullable |
| is_delivered | boolean | - | NN |
| is_canceled | boolean | - | NN |

dim_payment_method

| Column | PostgreSQL type | Key | Null |
| release_id | uuid | PK | NN |
| payment_method_key | bigint | PK | NN |
| source_system | text | - | NN |
| payment_type | text | - | nullable |

Metadata vật lý được gom để hình dễ đọc

Mọi bảng có lineage_id uuid, source_cut bigint, created_run_id uuid và last_changed_run_id uuid. Các dimensions còn có attribute_sha256 text. lineage_id nullable trong dimensions và NOT NULL trong facts; các trường kỹ thuật còn lại NOT NULL. Các FK của metadata trỏ tới ops/landing nằm ngoài core ERD này. Không vẽ chúng thành quan hệ dimension-fact.

Olist thực tế chỉ có snapshot; valid_from/valid_to của product là capability contract, không phải bằng chứng có lịch sử SCD2 thật. customer_unique_id là identity khách; buyer geography giữ ngữ cảnh địa chỉ của đơn. Không thêm tên khách/sản phẩm.


---

5 Order fact accumulating snapshot

fct_orders: một dòng cho (source_system, order_id). Physical PK = (release_id, order_key); unique business grain = (release_id, source_system, order_id). Giữ order khi thiếu items/payment, kèm flags. order_id là degenerate dimension.

fct_orders

| Column | PostgreSQL type | Key | Null |
| release_id | uuid | PK / FK | NN |
| order_key | text | PK | NN |
| source_system | text | - | NN |
| order_id | text | - | NN |
| customer_key | bigint | FK | NN |
| buyer_geography_key | bigint | FK | NN |
| order_status_key | bigint | FK | NN |
| purchase_date_key | integer | FK | NN |
| approved_date_key | integer | FK | NN |
| carrier_date_key | integer | FK | NN |
| delivered_date_key | integer | FK | NN |
| estimated_delivery_date_key | integer | FK | NN |
| source_customer_id | text | - | NN |
| purchase_timestamp | timestamp without time zone | - | NN |
| approved_timestamp | timestamp without time zone | - | nullable |
| carrier_timestamp | timestamp without time zone | - | nullable |
| delivered_timestamp | timestamp without time zone | - | nullable |
| estimated_delivery_timestamp | timestamp without time zone | - | NN |
| order_count | integer | - | NN |
| delivered_order_count | integer | - | NN |
| canceled_order_count | integer | - | NN |
| item_merchandise_total | numeric(18,2) | - | nullable |
| item_freight_total | numeric(18,2) | - | nullable |
| recorded_payment_total | numeric(18,2) | - | nullable |
| item_row_count | integer | - | NN |
| payment_record_count | integer | - | NN |
| has_items | boolean | - | NN |
| has_payments | boolean | - | NN |
| missing_delivery_timestamp | boolean | - | NN |
| temporal_anomaly | boolean | - | NN |
| known_delivery_date_count | integer | - | NN |
| on_time_delivery_count | integer | - | NN |
| purchase_to_delivery_seconds | numeric | - | nullable |
| currency_code | char(3) | - | NN |

Năm date FK cùng trỏ dim_date; timestamp không có timezone offset. Tiền là numeric/Decimal. Không SUM child totals sau khi join vào nhiều atomic item/payment rows. Audit columns chung ở trang 5 và file JSON.


---

6 Transaction facts

Mỗi fact giữ grain độc lập; không có fact-to-fact FK. Release_id là một phần PK và mọi dimensional FK.

fct_order_items

| Column | PostgreSQL type | Key | Null |
| release_id | uuid | PK / FK | NN |
| order_item_key | text | PK | NN |
| source_system | text | - | NN |
| order_id | text | - | NN |
| customer_key | bigint | FK | NN |
| buyer_geography_key | bigint | FK | NN |
| order_status_key | bigint | FK | NN |
| purchase_date_key | integer | FK | NN |
| product_key | bigint | FK | NN |
| seller_key | bigint | FK | NN |
| order_item_id | integer | - | NN |
| purchase_timestamp | timestamp without time zone | - | NN |
| merchandise_value | numeric(18,2) | - | NN |
| freight_value | numeric(18,2) | - | NN |
| item_row_count | integer | - | NN |
| currency_code | char(3) | - | NN |

fct_payments

| Column | PostgreSQL type | Key | Null |
| release_id | uuid | PK / FK | NN |
| payment_key | text | PK | NN |
| source_system | text | - | NN |
| order_id | text | - | NN |
| customer_key | bigint | FK | NN |
| buyer_geography_key | bigint | FK | NN |
| order_status_key | bigint | FK | NN |
| purchase_date_key | integer | FK | NN |
| payment_method_key | bigint | FK | NN |
| payment_sequential | integer | - | NN |
| purchase_timestamp | timestamp without time zone | - | NN |
| recorded_payment_value | numeric(18,2) | - | NN |
| payment_installments | integer | - | NN |
| payment_record_count | integer | - | NN |
| currency_code | char(3) | - | NN |

Items unique: release + source + order_id + order_item_id. Payments unique: release + source + order_id + payment_sequential. order_item_id là line ordinal, không phải quantity; payment_installments không phải measure cộng dồn. Purchase date trên payment là ngữ cảnh đơn, không phải payment event time.


---

7 Danh sách chính xác 19 FK roles

Tất cả connector biểu diễn (release_id, fact_role_key) → (release_id, dimension_key). Crow’s foot ở phía fact; một dimension member có thể được nhiều fact rows tham chiếu. Không nối facts chỉ vì cùng order_id.

| Fact | FK role | Dimension |
| fct_orders | customer_key | dim_customer |
| fct_orders | buyer_geography_key | dim_buyer_geography |
| fct_orders | order_status_key | dim_order_status |
| fct_orders | purchase_date_key | dim_date |
| fct_orders | approved_date_key | dim_date |
| fct_orders | carrier_date_key | dim_date |
| fct_orders | delivered_date_key | dim_date |
| fct_orders | estimated_delivery_date_key | dim_date |
| fct_order_items | customer_key | dim_customer |
| fct_order_items | buyer_geography_key | dim_buyer_geography |
| fct_order_items | order_status_key | dim_order_status |
| fct_order_items | purchase_date_key | dim_date |
| fct_order_items | product_key | dim_product |
| fct_order_items | seller_key | dim_seller |
| fct_payments | customer_key | dim_customer |
| fct_payments | buyer_geography_key | dim_buyer_geography |
| fct_payments | order_status_key | dim_order_status |
| fct_payments | purchase_date_key | dim_date |
| fct_payments | payment_method_key | dim_payment_method |

Grain và business identity

| Fact | Grain không gồm technical release |
| fct_orders | source_system + order_id |
| fct_order_items | source_system + order_id + order_item_id |
| fct_payments | source_system + order_id + payment_sequential |

Fact keys order_key/order_item_key/payment_key là text trong implementation; chỉ dimension SKs là warehouse-managed integer. Reserved members: 0 Unknown, -1 N/A. Inferred members giữ integer SK khi bổ sung attributes.


---

8 Control data flow và kiểm ảnh

Node và mũi tên kiến trúc không được tự đổi

| Quan hệ | Ý nghĩa |
| Olist → Python → MinIO | Giữ source-native raw và checksum; không làm giàu dữ liệu tại MinIO |
| MinIO → Python → landing | Đọc/replay raw; validate trước admission; accepted source versions và fixed source_cut |
| landing → dbt → work | Staging/intermediate; 7 dims, 3 facts; tests và registry |
| work → controlled snapshot → warehouse_store | Copy đầy đủ vào immutable release; FK/grain/reconciliation gates |
| warehouse_store → semantic_input → MetricFlow → reporting | Bind release trên từng connection; execute SQL; lưu 5 metric exports |
| published Kimball → reporting.analytic_* | SQL views cho customer/cohort/delivery/payment, không giả là MetricFlow metrics |
| publication gate → published reporting → Superset | Chỉ khi checks/parity đạt; readonly và mọi chart pin cùng release |
| Airflow - - → execution tasks | Dashed control arrows; raw/validate/load/lease/build/snapshot/semantic/publish/finish |

Review prompt

Before rendering, extract the required nodes, table names, PKs, unique grains and all nineteen dimensional FK roles from the brief. Compare them with your planned drawing and report any ambiguity. Preserve the supplied architecture rather than replacing it with a generic modern data stack. After rendering, check that every label is spelled correctly, all arrows match the brief, and no unimplemented component or fact-to-fact relationship was introduced. If image generation cannot reproduce dense schema text reliably, output editable SVG or diagram code with exact text instead of inventing labels. Generate the architecture and ERD as two separate deliverables, not one combined poster.

Checklist: đúng 10 bảng; đúng datatype và 19 FK roles; không fact-to-fact; không gộp PostgreSQL schemas thành nhiều DWH; không native Superset–MetricFlow API; không tự thêm stack trong ảnh mẫu. Official logos chỉ là nhãn công nghệ, không ngụ ý affiliation. Không dùng logo Abbott/Concentrix.

Sources: infra/compose.yaml; orchestration/dags/sales_warehouse_pipeline.py; contracts/warehouse-model.json; db/migrations/001_schema.sql và 005_published_analysis.sql; src/sales_dw/export_metrics.py; README.md. Schema JSON giữ SHA-256 migration. Đây là tài liệu đọc từ code, không chạy DDL/SQL hoặc tái nghiệm thu runtime.
