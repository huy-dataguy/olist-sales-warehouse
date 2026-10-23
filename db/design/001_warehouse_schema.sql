-- DESIGN-ONLY PostgreSQL DDL. NOT APPLIED.
-- Turn this reviewed schema into controlled versioned migrations before execution.
-- No passwords, source history fabrication or production reset is included.
BEGIN;

CREATE SCHEMA ops;
CREATE SCHEMA landing;
CREATE SCHEMA work;
CREATE SCHEMA warehouse_store;
CREATE SCHEMA warehouse;
CREATE SCHEMA semantic_input;
CREATE SCHEMA reporting;
CREATE EXTENSION btree_gist WITH SCHEMA ops;
SET LOCAL search_path = pg_catalog, ops;

REVOKE ALL ON SCHEMA ops, landing, work, warehouse_store, semantic_input FROM PUBLIC;

CREATE TABLE ops.pipeline_runs (
    pipeline_run_id uuid PRIMARY KEY,
    airflow_run_id text,
    state text NOT NULL CHECK (state IN ('created','running','failed','succeeded')),
    source_cut bigint,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    error_category text,
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);
CREATE TABLE ops.artifacts (
    artifact_sha256 text PRIMARY KEY CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
    source_system text NOT NULL,
    source_version text NOT NULL,
    object_bucket text NOT NULL,
    object_key text NOT NULL UNIQUE,
    content_bytes bigint NOT NULL CHECK (content_bytes >= 0),
    state text NOT NULL CHECK (state IN ('discovered','preserved','unavailable')),
    captured_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    preserved_at timestamptz,
    CHECK (state <> 'preserved' OR preserved_at IS NOT NULL)
);
CREATE TABLE ops.batches (
    batch_id text PRIMARY KEY,
    replay_plan_id text NOT NULL,
    artifact_sha256 text NOT NULL REFERENCES ops.artifacts,
    batch_sequence bigint NOT NULL CHECK (batch_sequence > 0),
    schema_version text NOT NULL,
    scenario_id text,
    state text NOT NULL CHECK (state IN ('discovered','raw_preserved','validated','loaded','failed')),
    received_occurrences bigint NOT NULL DEFAULT 0 CHECK (received_occurrences >= 0),
    accepted_occurrences bigint NOT NULL DEFAULT 0 CHECK (accepted_occurrences >= 0),
    duplicate_occurrences bigint NOT NULL DEFAULT 0 CHECK (duplicate_occurrences >= 0),
    rejected_occurrences bigint NOT NULL DEFAULT 0 CHECK (rejected_occurrences >= 0),
    UNIQUE (artifact_sha256, replay_plan_id, batch_sequence)
);
CREATE TABLE ops.receipts (
    receipt_id uuid PRIMARY KEY,
    batch_id text NOT NULL REFERENCES ops.batches,
    pipeline_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    attempt integer NOT NULL CHECK (attempt > 0),
    state text NOT NULL CHECK (state IN ('received','accepted','duplicate','rejected'))
);
CREATE TABLE ops.source_commits (
    source_cut bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id text NOT NULL UNIQUE REFERENCES ops.batches,
    committed_by_run uuid NOT NULL REFERENCES ops.pipeline_runs,
    captured_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
-- Admission is serialized/fenced. Sequence allocation alone is not commit ordering.
CREATE TABLE landing.source_versions (
    source_version_id uuid PRIMARY KEY,
    source_cut bigint NOT NULL REFERENCES ops.source_commits,
    entity text NOT NULL,
    natural_key text NOT NULL,
    declared_revision text,
    revision_provenance text NOT NULL,
    payload jsonb NOT NULL,
    record_sha256 text NOT NULL CHECK (record_sha256 ~ '^[0-9a-f]{64}$'),
    artifact_sha256 text NOT NULL REFERENCES ops.artifacts,
    file_member text NOT NULL,
    source_row_number bigint NOT NULL CHECK (source_row_number > 0),
    UNIQUE (source_cut, entity, natural_key)
);
CREATE INDEX source_versions_at_cut ON landing.source_versions (entity, natural_key, source_cut DESC);
CREATE TABLE ops.dimension_key_registry (
    surrogate_key bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    namespace text NOT NULL,
    natural_key text NOT NULL,
    version_identity text NOT NULL,
    allocated_by_run uuid NOT NULL REFERENCES ops.pipeline_runs,
    UNIQUE (namespace, natural_key, version_identity),
    CHECK (surrogate_key > 0)
);
CREATE TABLE ops.pipeline_leases (
    lease_name text PRIMARY KEY,
    owner_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    fencing_token bigint NOT NULL CHECK (fencing_token > 0),
    heartbeat_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    CHECK (expires_at > heartbeat_at)
);
CREATE TABLE ops.model_checkpoints (
    model_name text PRIMARY KEY,
    source_cut bigint NOT NULL REFERENCES ops.source_commits,
    successful_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    model_version text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE ops.releases (
    release_id uuid PRIMARY KEY,
    pipeline_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    source_cut bigint NOT NULL REFERENCES ops.source_commits,
    contract_version text NOT NULL,
    model_version text NOT NULL,
    semantic_manifest_sha256 text CHECK (semantic_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    fencing_token bigint NOT NULL CHECK (fencing_token > 0),
    state text NOT NULL CHECK (state IN ('building','warehouse_validated','snapshotted','metrics_validated','published','failed')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    published_at timestamptz
);
CREATE TABLE ops.check_results (
    release_id uuid NOT NULL REFERENCES ops.releases,
    check_id text NOT NULL,
    state text NOT NULL CHECK (state IN ('pending','passed','failed')),
    evidence_uri text NOT NULL,
    checked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (release_id, check_id)
);
CREATE TABLE ops.snapshot_relations (
    release_id uuid NOT NULL REFERENCES ops.releases,
    model_name text NOT NULL,
    row_count bigint NOT NULL CHECK (row_count >= 0),
    logical_content_sha256 text NOT NULL CHECK (logical_content_sha256 ~ '^[0-9a-f]{64}$'),
    validated boolean NOT NULL,
    PRIMARY KEY (release_id, model_name)
);
CREATE TABLE ops.lineage_edges (
    release_id uuid NOT NULL REFERENCES ops.releases,
    model_name text NOT NULL,
    derived_natural_key text NOT NULL,
    source_version_id uuid NOT NULL REFERENCES landing.source_versions,
    input_role text NOT NULL,
    PRIMARY KEY (release_id, model_name, derived_natural_key, source_version_id, input_role)
);
CREATE TABLE ops.export_queries (
    release_id uuid NOT NULL REFERENCES ops.releases,
    export_id text NOT NULL,
    semantic_manifest_sha256 text NOT NULL CHECK (semantic_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    generated_sql_sha256 text NOT NULL CHECK (generated_sql_sha256 ~ '^[0-9a-f]{64}$'),
    generated_sql text NOT NULL,
    query_parameters jsonb NOT NULL,
    result_row_count bigint NOT NULL CHECK (result_row_count >= 0),
    logical_result_sha256 text NOT NULL CHECK (logical_result_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (release_id, export_id)
);
CREATE TABLE ops.published_release (
    channel text PRIMARY KEY CHECK (channel = 'main'),
    release_id uuid NOT NULL REFERENCES ops.releases,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE ops.dq_issues (
    issue_id uuid PRIMARY KEY,
    pipeline_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    release_id uuid REFERENCES ops.releases,
    batch_id text REFERENCES ops.batches,
    source_version_id uuid REFERENCES landing.source_versions,
    rule_id text NOT NULL,
    severity text NOT NULL CHECK (severity IN ('warning','error')),
    reason_code text NOT NULL,
    entity text NOT NULL,
    natural_key text,
    scope_key text NOT NULL,
    affected_records bigint NOT NULL DEFAULT 1 CHECK (affected_records > 0),
    redacted_details jsonb NOT NULL,
    detected_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (pipeline_run_id, rule_id, entity, scope_key)
);
CREATE TABLE ops.state_events (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    release_id uuid REFERENCES ops.releases,
    actor_role text NOT NULL,
    previous_state text,
    new_state text NOT NULL,
    reason text NOT NULL,
    fencing_token bigint,
    event_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE warehouse_store.dim_customer (
    release_id uuid NOT NULL REFERENCES ops.releases,
    customer_key bigint NOT NULL CHECK (customer_key >= -1),
    source_system text NOT NULL,
    customer_unique_id text,
    is_inferred boolean NOT NULL DEFAULT false,
    attribute_sha256 text NOT NULL CHECK (attribute_sha256 ~ '^[0-9a-f]{64}$'),
    lineage_id uuid REFERENCES landing.source_versions(source_version_id),
    created_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    last_changed_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    source_cut bigint NOT NULL REFERENCES ops.source_commits,
    PRIMARY KEY (release_id, customer_key),
    UNIQUE (release_id, source_system, customer_unique_id),
    CHECK (customer_key <= 0 OR lineage_id IS NOT NULL OR source_system = 'system')
);

CREATE TABLE warehouse_store.dim_product (
    release_id uuid NOT NULL REFERENCES ops.releases,
    product_key bigint NOT NULL CHECK (product_key >= -1),
    source_system text NOT NULL,
    product_id text,
    version_identity text NOT NULL,
    category_source text,
    category_english text,
    category text NOT NULL,
    category_missing boolean NOT NULL,
    valid_from timestamp without time zone,
    valid_to timestamp without time zone,
    is_current boolean NOT NULL,
    business_effectivity_known boolean NOT NULL DEFAULT false,
    is_inferred boolean NOT NULL DEFAULT false,
    attribute_sha256 text NOT NULL CHECK (attribute_sha256 ~ '^[0-9a-f]{64}$'),
    lineage_id uuid REFERENCES landing.source_versions(source_version_id),
    created_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    last_changed_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    source_cut bigint NOT NULL REFERENCES ops.source_commits,
    PRIMARY KEY (release_id, product_key),
    UNIQUE (release_id, source_system, product_id, version_identity),
    CHECK (product_key <= 0 OR lineage_id IS NOT NULL OR source_system = 'system'),
    CHECK (valid_to IS NULL OR valid_from IS NOT NULL AND valid_to > valid_from),
    CHECK (NOT business_effectivity_known OR valid_from IS NOT NULL),
    CHECK (product_key <= 0 OR is_current = (valid_to IS NULL)),
    EXCLUDE USING gist (
        release_id WITH =,
        source_system WITH =,
        product_id WITH =,
        tsrange(valid_from, valid_to, '[)') WITH &&
    ) WHERE (business_effectivity_known AND product_key > 0)
);

CREATE TABLE warehouse_store.dim_seller (
    release_id uuid NOT NULL REFERENCES ops.releases,
    seller_key bigint NOT NULL CHECK (seller_key >= -1),
    source_system text NOT NULL,
    seller_id text,
    seller_city text,
    seller_state text,
    seller_zip_code_prefix text,
    is_inferred boolean NOT NULL DEFAULT false,
    attribute_sha256 text NOT NULL CHECK (attribute_sha256 ~ '^[0-9a-f]{64}$'),
    lineage_id uuid REFERENCES landing.source_versions(source_version_id),
    created_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    last_changed_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    source_cut bigint NOT NULL REFERENCES ops.source_commits,
    PRIMARY KEY (release_id, seller_key),
    UNIQUE (release_id, source_system, seller_id),
    CHECK (seller_key <= 0 OR lineage_id IS NOT NULL OR source_system = 'system')
);

CREATE TABLE warehouse_store.dim_buyer_geography (
    release_id uuid NOT NULL REFERENCES ops.releases,
    buyer_geography_key bigint NOT NULL CHECK (buyer_geography_key >= -1),
    source_system text NOT NULL,
    postal_prefix text,
    city text,
    state text,
    attribute_sha256 text NOT NULL CHECK (attribute_sha256 ~ '^[0-9a-f]{64}$'),
    lineage_id uuid REFERENCES landing.source_versions(source_version_id),
    created_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    last_changed_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    source_cut bigint NOT NULL REFERENCES ops.source_commits,
    PRIMARY KEY (release_id, buyer_geography_key),
    UNIQUE (release_id, source_system, postal_prefix, city, state),
    CHECK (buyer_geography_key <= 0 OR lineage_id IS NOT NULL OR source_system = 'system')
);

CREATE TABLE warehouse_store.dim_date (
    release_id uuid NOT NULL REFERENCES ops.releases,
    date_key integer NOT NULL CHECK (date_key >= -1),
    source_system text NOT NULL,
    full_date date,
    month_start date,
    day smallint,
    month smallint,
    quarter smallint,
    year smallint,
    weekday smallint,
    attribute_sha256 text NOT NULL CHECK (attribute_sha256 ~ '^[0-9a-f]{64}$'),
    lineage_id uuid REFERENCES landing.source_versions(source_version_id),
    created_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    last_changed_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    source_cut bigint NOT NULL REFERENCES ops.source_commits,
    PRIMARY KEY (release_id, date_key),
    UNIQUE (release_id, full_date),
    CHECK (date_key <= 0 OR lineage_id IS NOT NULL OR source_system = 'system')
);

CREATE TABLE warehouse_store.dim_order_status (
    release_id uuid NOT NULL REFERENCES ops.releases,
    order_status_key bigint NOT NULL CHECK (order_status_key >= -1),
    source_system text NOT NULL,
    status_code text,
    is_delivered boolean NOT NULL,
    is_canceled boolean NOT NULL,
    attribute_sha256 text NOT NULL CHECK (attribute_sha256 ~ '^[0-9a-f]{64}$'),
    lineage_id uuid REFERENCES landing.source_versions(source_version_id),
    created_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    last_changed_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    source_cut bigint NOT NULL REFERENCES ops.source_commits,
    PRIMARY KEY (release_id, order_status_key),
    UNIQUE (release_id, source_system, status_code),
    CHECK (order_status_key <= 0 OR lineage_id IS NOT NULL OR source_system = 'system'),
    CHECK (NOT (is_delivered AND is_canceled))
);

CREATE TABLE warehouse_store.dim_payment_method (
    release_id uuid NOT NULL REFERENCES ops.releases,
    payment_method_key bigint NOT NULL CHECK (payment_method_key >= -1),
    source_system text NOT NULL,
    payment_type text,
    attribute_sha256 text NOT NULL CHECK (attribute_sha256 ~ '^[0-9a-f]{64}$'),
    lineage_id uuid REFERENCES landing.source_versions(source_version_id),
    created_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    last_changed_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    source_cut bigint NOT NULL REFERENCES ops.source_commits,
    PRIMARY KEY (release_id, payment_method_key),
    UNIQUE (release_id, source_system, payment_type),
    CHECK (payment_method_key <= 0 OR lineage_id IS NOT NULL OR source_system = 'system')
);

CREATE UNIQUE INDEX product_one_current_version
    ON warehouse_store.dim_product (release_id, source_system, product_id)
    WHERE is_current AND product_key > 0;

CREATE TABLE warehouse_store.fct_orders (
    release_id uuid NOT NULL REFERENCES ops.releases,
    order_key text NOT NULL,
    source_system text NOT NULL,
    order_id text NOT NULL,
    customer_key bigint NOT NULL,
    buyer_geography_key bigint NOT NULL,
    order_status_key bigint NOT NULL,
    purchase_date_key integer NOT NULL,
    approved_date_key integer NOT NULL,
    carrier_date_key integer NOT NULL,
    delivered_date_key integer NOT NULL,
    estimated_delivery_date_key integer NOT NULL,
    source_customer_id text NOT NULL,
    purchase_timestamp timestamp without time zone NOT NULL,
    approved_timestamp timestamp without time zone,
    carrier_timestamp timestamp without time zone,
    delivered_timestamp timestamp without time zone,
    estimated_delivery_timestamp timestamp without time zone NOT NULL,
    order_count integer NOT NULL CHECK (order_count = 1),
    delivered_order_count integer NOT NULL CHECK (delivered_order_count IN (0,1)),
    canceled_order_count integer NOT NULL CHECK (canceled_order_count IN (0,1)),
    item_merchandise_total numeric(18,2),
    item_freight_total numeric(18,2),
    recorded_payment_total numeric(18,2),
    item_row_count integer NOT NULL CHECK (item_row_count >= 0),
    payment_record_count integer NOT NULL CHECK (payment_record_count >= 0),
    has_items boolean NOT NULL,
    has_payments boolean NOT NULL,
    missing_delivery_timestamp boolean NOT NULL,
    temporal_anomaly boolean NOT NULL,
    known_delivery_date_count integer NOT NULL CHECK (known_delivery_date_count IN (0,1)),
    on_time_delivery_count integer NOT NULL CHECK (on_time_delivery_count IN (0,1)),
    purchase_to_delivery_seconds numeric CHECK (purchase_to_delivery_seconds >= 0),
    currency_code char(3) NOT NULL CHECK (currency_code = 'BRL'),
    lineage_id uuid NOT NULL REFERENCES landing.source_versions(source_version_id),
    source_cut bigint NOT NULL REFERENCES ops.source_commits,
    created_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    last_changed_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    PRIMARY KEY (release_id, order_key),
    UNIQUE (release_id, source_system, order_id),
    FOREIGN KEY (release_id, customer_key) REFERENCES warehouse_store.dim_customer (release_id, customer_key),
    FOREIGN KEY (release_id, buyer_geography_key) REFERENCES warehouse_store.dim_buyer_geography (release_id, buyer_geography_key),
    FOREIGN KEY (release_id, order_status_key) REFERENCES warehouse_store.dim_order_status (release_id, order_status_key),
    FOREIGN KEY (release_id, purchase_date_key) REFERENCES warehouse_store.dim_date (release_id, date_key),
    FOREIGN KEY (release_id, approved_date_key) REFERENCES warehouse_store.dim_date (release_id, date_key),
    FOREIGN KEY (release_id, carrier_date_key) REFERENCES warehouse_store.dim_date (release_id, date_key),
    FOREIGN KEY (release_id, delivered_date_key) REFERENCES warehouse_store.dim_date (release_id, date_key),
    FOREIGN KEY (release_id, estimated_delivery_date_key) REFERENCES warehouse_store.dim_date (release_id, date_key),
    CHECK (delivered_order_count + canceled_order_count <= 1),
    CHECK (on_time_delivery_count <= known_delivery_date_count),
    CHECK (has_items = (item_row_count > 0)),
    CHECK (has_payments = (payment_record_count > 0))
);
CREATE INDEX fct_orders_purchase_date ON warehouse_store.fct_orders (release_id, purchase_date_key);

CREATE TABLE warehouse_store.fct_order_items (
    release_id uuid NOT NULL REFERENCES ops.releases,
    order_item_key text NOT NULL,
    source_system text NOT NULL,
    order_id text NOT NULL,
    customer_key bigint NOT NULL,
    buyer_geography_key bigint NOT NULL,
    order_status_key bigint NOT NULL,
    purchase_date_key integer NOT NULL,
    product_key bigint NOT NULL,
    seller_key bigint NOT NULL,
    order_item_id integer NOT NULL CHECK (order_item_id > 0),
    purchase_timestamp timestamp without time zone NOT NULL,
    merchandise_value numeric(18,2) NOT NULL CHECK (merchandise_value >= 0),
    freight_value numeric(18,2) NOT NULL CHECK (freight_value >= 0),
    item_row_count integer NOT NULL CHECK (item_row_count = 1),
    currency_code char(3) NOT NULL CHECK (currency_code = 'BRL'),
    lineage_id uuid NOT NULL REFERENCES landing.source_versions(source_version_id),
    source_cut bigint NOT NULL REFERENCES ops.source_commits,
    created_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    last_changed_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    PRIMARY KEY (release_id, order_item_key),
    UNIQUE (release_id, source_system, order_id, order_item_id),
    FOREIGN KEY (release_id, customer_key) REFERENCES warehouse_store.dim_customer (release_id, customer_key),
    FOREIGN KEY (release_id, buyer_geography_key) REFERENCES warehouse_store.dim_buyer_geography (release_id, buyer_geography_key),
    FOREIGN KEY (release_id, order_status_key) REFERENCES warehouse_store.dim_order_status (release_id, order_status_key),
    FOREIGN KEY (release_id, purchase_date_key) REFERENCES warehouse_store.dim_date (release_id, date_key),
    FOREIGN KEY (release_id, product_key) REFERENCES warehouse_store.dim_product (release_id, product_key),
    FOREIGN KEY (release_id, seller_key) REFERENCES warehouse_store.dim_seller (release_id, seller_key)
);
CREATE INDEX fct_order_items_purchase_date ON warehouse_store.fct_order_items (release_id, purchase_date_key);

CREATE TABLE warehouse_store.fct_payments (
    release_id uuid NOT NULL REFERENCES ops.releases,
    payment_key text NOT NULL,
    source_system text NOT NULL,
    order_id text NOT NULL,
    customer_key bigint NOT NULL,
    buyer_geography_key bigint NOT NULL,
    order_status_key bigint NOT NULL,
    purchase_date_key integer NOT NULL,
    payment_method_key bigint NOT NULL,
    payment_sequential integer NOT NULL CHECK (payment_sequential > 0),
    purchase_timestamp timestamp without time zone NOT NULL,
    recorded_payment_value numeric(18,2) NOT NULL CHECK (recorded_payment_value >= 0),
    payment_installments integer NOT NULL CHECK (payment_installments >= 0),
    payment_record_count integer NOT NULL CHECK (payment_record_count = 1),
    currency_code char(3) NOT NULL CHECK (currency_code = 'BRL'),
    lineage_id uuid NOT NULL REFERENCES landing.source_versions(source_version_id),
    source_cut bigint NOT NULL REFERENCES ops.source_commits,
    created_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    last_changed_run_id uuid NOT NULL REFERENCES ops.pipeline_runs,
    PRIMARY KEY (release_id, payment_key),
    UNIQUE (release_id, source_system, order_id, payment_sequential),
    FOREIGN KEY (release_id, customer_key) REFERENCES warehouse_store.dim_customer (release_id, customer_key),
    FOREIGN KEY (release_id, buyer_geography_key) REFERENCES warehouse_store.dim_buyer_geography (release_id, buyer_geography_key),
    FOREIGN KEY (release_id, order_status_key) REFERENCES warehouse_store.dim_order_status (release_id, order_status_key),
    FOREIGN KEY (release_id, purchase_date_key) REFERENCES warehouse_store.dim_date (release_id, date_key),
    FOREIGN KEY (release_id, payment_method_key) REFERENCES warehouse_store.dim_payment_method (release_id, payment_method_key)
);
CREATE INDEX fct_payments_purchase_date ON warehouse_store.fct_payments (release_id, purchase_date_key);

CREATE TABLE reporting.sales_monthly (
    release_id uuid NOT NULL REFERENCES ops.releases,
    month date NOT NULL,
    total_orders bigint NOT NULL CHECK (total_orders >= 0),
    delivered_orders bigint NOT NULL CHECK (delivered_orders >= 0),
    canceled_orders bigint NOT NULL CHECK (canceled_orders >= 0),
    cancellation_rate double precision,
    delivered_merchandise_value numeric(18,2) NOT NULL,
    delivered_aov double precision,
    delivered_unique_customers bigint NOT NULL CHECK (delivered_unique_customers >= 0),
    delivered_item_rows bigint NOT NULL CHECK (delivered_item_rows >= 0),
    generated_sql_sha256 text NOT NULL CHECK (generated_sql_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (release_id, month)
);

CREATE TABLE reporting.sales_daily (
    release_id uuid NOT NULL REFERENCES ops.releases,
    day date NOT NULL,
    total_orders bigint NOT NULL CHECK (total_orders >= 0),
    delivered_orders bigint NOT NULL CHECK (delivered_orders >= 0),
    canceled_orders bigint NOT NULL CHECK (canceled_orders >= 0),
    delivered_merchandise_value numeric(18,2) NOT NULL,
    delivered_item_rows bigint NOT NULL CHECK (delivered_item_rows >= 0),
    generated_sql_sha256 text NOT NULL CHECK (generated_sql_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (release_id, day)
);

CREATE TABLE reporting.product_monthly (
    release_id uuid NOT NULL REFERENCES ops.releases,
    month date NOT NULL,
    category text NOT NULL,
    delivered_merchandise_value numeric(18,2) NOT NULL,
    delivered_item_rows bigint NOT NULL CHECK (delivered_item_rows >= 0),
    generated_sql_sha256 text NOT NULL CHECK (generated_sql_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (release_id, month, category)
);

CREATE TABLE reporting.seller_monthly (
    release_id uuid NOT NULL REFERENCES ops.releases,
    month date NOT NULL,
    seller_id text NOT NULL,
    delivered_merchandise_value numeric(18,2) NOT NULL,
    delivered_item_rows bigint NOT NULL CHECK (delivered_item_rows >= 0),
    generated_sql_sha256 text NOT NULL CHECK (generated_sql_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (release_id, month, seller_id)
);

CREATE TABLE reporting.buyer_state_monthly (
    release_id uuid NOT NULL REFERENCES ops.releases,
    month date NOT NULL,
    state text NOT NULL,
    total_orders bigint NOT NULL CHECK (total_orders >= 0),
    delivered_orders bigint NOT NULL CHECK (delivered_orders >= 0),
    canceled_orders bigint NOT NULL CHECK (canceled_orders >= 0),
    cancellation_rate double precision,
    delivered_merchandise_value numeric(18,2) NOT NULL,
    delivered_aov double precision,
    delivered_unique_customers bigint NOT NULL CHECK (delivered_unique_customers >= 0),
    delivered_item_rows bigint NOT NULL CHECK (delivered_item_rows >= 0),
    generated_sql_sha256 text NOT NULL CHECK (generated_sql_sha256 ~ '^[0-9a-f]{64}$'),
    PRIMARY KEY (release_id, month, state)
);

CREATE VIEW warehouse.dim_customer AS
SELECT s.* FROM warehouse_store.dim_customer s
JOIN ops.published_release p ON p.release_id = s.release_id AND p.channel = 'main';

CREATE VIEW warehouse.dim_product AS
SELECT s.* FROM warehouse_store.dim_product s
JOIN ops.published_release p ON p.release_id = s.release_id AND p.channel = 'main';

CREATE VIEW warehouse.dim_seller AS
SELECT s.* FROM warehouse_store.dim_seller s
JOIN ops.published_release p ON p.release_id = s.release_id AND p.channel = 'main';

CREATE VIEW warehouse.dim_buyer_geography AS
SELECT s.* FROM warehouse_store.dim_buyer_geography s
JOIN ops.published_release p ON p.release_id = s.release_id AND p.channel = 'main';

CREATE VIEW warehouse.dim_date AS
SELECT s.* FROM warehouse_store.dim_date s
JOIN ops.published_release p ON p.release_id = s.release_id AND p.channel = 'main';

CREATE VIEW warehouse.dim_order_status AS
SELECT s.* FROM warehouse_store.dim_order_status s
JOIN ops.published_release p ON p.release_id = s.release_id AND p.channel = 'main';

CREATE VIEW warehouse.dim_payment_method AS
SELECT s.* FROM warehouse_store.dim_payment_method s
JOIN ops.published_release p ON p.release_id = s.release_id AND p.channel = 'main';

CREATE VIEW warehouse.fct_orders AS
SELECT s.* FROM warehouse_store.fct_orders s
JOIN ops.published_release p ON p.release_id = s.release_id AND p.channel = 'main';

CREATE VIEW warehouse.fct_order_items AS
SELECT s.* FROM warehouse_store.fct_order_items s
JOIN ops.published_release p ON p.release_id = s.release_id AND p.channel = 'main';

CREATE VIEW warehouse.fct_payments AS
SELECT s.* FROM warehouse_store.fct_payments s
JOIN ops.published_release p ON p.release_id = s.release_id AND p.channel = 'main';

CREATE VIEW semantic_input.fct_orders AS
SELECT s.* FROM warehouse_store.fct_orders s
WHERE s.release_id = current_setting('sales_dw.candidate_release_id')::uuid;

CREATE VIEW semantic_input.fct_order_items AS
SELECT s.* FROM warehouse_store.fct_order_items s
WHERE s.release_id = current_setting('sales_dw.candidate_release_id')::uuid;

CREATE VIEW semantic_input.fct_payments AS
SELECT s.* FROM warehouse_store.fct_payments s
WHERE s.release_id = current_setting('sales_dw.candidate_release_id')::uuid;

CREATE VIEW semantic_input.dim_customer AS
SELECT s.* FROM warehouse_store.dim_customer s
WHERE s.release_id = current_setting('sales_dw.candidate_release_id')::uuid;

CREATE VIEW semantic_input.dim_product AS
SELECT s.* FROM warehouse_store.dim_product s
WHERE s.release_id = current_setting('sales_dw.candidate_release_id')::uuid;

CREATE VIEW semantic_input.dim_seller AS
SELECT s.* FROM warehouse_store.dim_seller s
WHERE s.release_id = current_setting('sales_dw.candidate_release_id')::uuid;

CREATE VIEW semantic_input.dim_buyer_geography AS
SELECT s.* FROM warehouse_store.dim_buyer_geography s
WHERE s.release_id = current_setting('sales_dw.candidate_release_id')::uuid;

CREATE VIEW semantic_input.dim_date AS
SELECT s.* FROM warehouse_store.dim_date s
WHERE s.release_id = current_setting('sales_dw.candidate_release_id')::uuid;

CREATE VIEW semantic_input.dim_order_status AS
SELECT s.* FROM warehouse_store.dim_order_status s
WHERE s.release_id = current_setting('sales_dw.candidate_release_id')::uuid;

CREATE VIEW semantic_input.dim_payment_method AS
SELECT s.* FROM warehouse_store.dim_payment_method s
WHERE s.release_id = current_setting('sales_dw.candidate_release_id')::uuid;

CREATE VIEW reporting.validated_sales_monthly AS
SELECT e.* FROM reporting.sales_monthly e
JOIN ops.releases r ON r.release_id = e.release_id
WHERE r.state = 'published';

CREATE VIEW reporting.validated_sales_daily AS
SELECT e.* FROM reporting.sales_daily e
JOIN ops.releases r ON r.release_id = e.release_id
WHERE r.state = 'published';

CREATE VIEW reporting.validated_product_monthly AS
SELECT e.* FROM reporting.product_monthly e
JOIN ops.releases r ON r.release_id = e.release_id
WHERE r.state = 'published';

CREATE VIEW reporting.validated_seller_monthly AS
SELECT e.* FROM reporting.seller_monthly e
JOIN ops.releases r ON r.release_id = e.release_id
WHERE r.state = 'published';

CREATE VIEW reporting.validated_buyer_state_monthly AS
SELECT e.* FROM reporting.buyer_state_monthly e
JOIN ops.releases r ON r.release_id = e.release_id
WHERE r.state = 'published';

CREATE VIEW reporting.pipeline_health AS
SELECT pipeline_run_id, airflow_run_id, state, source_cut, started_at, finished_at,
       error_category
FROM ops.pipeline_runs;

CREATE VIEW reporting.release_metadata AS
SELECT release_id, source_cut, contract_version, model_version, state,
       created_at, published_at
FROM ops.releases
WHERE state = 'published';

CREATE VIEW reporting.quality_health AS
SELECT pipeline_run_id, release_id, rule_id, severity,
       SUM(affected_records) AS affected_records
FROM ops.dq_issues
GROUP BY pipeline_run_id, release_id, rule_id, severity;

-- Publisher transaction contract (implemented later through controlled code):
-- 1. Lock lease and reject stale owner/fencing token/expiry.
-- 2. Lock candidate release; require its immutable snapshot and all required checks.
-- 3. Require complete metric exports and parity at the same source_cut/release_id.
-- 4. Mark published and UPSERT ops.published_release in this transaction.
-- 5. Append state_events and commit. Retry recognizes an existing identical commit.
-- No direct fact-to-fact foreign keys or atomic reporting joins are defined.
COMMIT;

