"""Independent Warehouse assertions and source-aware warnings, not fabricated balancing."""
from decimal import Decimal
from uuid import uuid5, NAMESPACE_URL

from psycopg import sql
from psycopg.types.json import Jsonb

from .config import context

MODELS = {
    "dim_customer": "customer_key", "dim_product": "product_key", "dim_seller": "seller_key",
    "dim_buyer_geography": "buyer_geography_key", "dim_date": "date_key",
    "dim_order_status": "order_status_key", "dim_payment_method": "payment_method_key",
    "fct_orders": "order_key", "fct_order_items": "order_item_key", "fct_payments": "payment_key",
}


def logical_hash(conn, schema, model):
    key = MODELS[model]
    return conn.execute(sql.SQL("""SELECT count(*) AS n, encode(sha256(convert_to(coalesce(
      string_agg(md5((to_jsonb(s)-ARRAY['release_id','source_cut','created_run_id','last_changed_run_id'])::text),'' ORDER BY {}),''),'UTF8')),'hex') AS sha
      FROM {}.{} s""").format(sql.Identifier(key), sql.Identifier(schema), sql.Identifier(model))).fetchone()


def check_work(conn, run_id):
    ctx = context(run_id)
    cut = ctx["source_cut"]
    results = {}
    for model, key in MODELS.items():
        row = conn.execute(sql.SQL("SELECT count(*) AS n,count(DISTINCT {}) AS keys,count(*) FILTER(WHERE source_cut>%s) AS future FROM work.{}").format(sql.Identifier(key), sql.Identifier(model)), (cut,)).fetchone()
        assert row["n"] == row["keys"] and row["future"] == 0, (model, row)
        checkpoint = conn.execute("SELECT source_cut FROM ops.model_checkpoints WHERE model_name=%s", (model,)).fetchone()
        assert checkpoint and checkpoint["source_cut"] == cut, (model, "checkpoint mismatch")
        results[model] = row["n"]
    for entity, model in (("orders", "fct_orders"), ("order_items", "fct_order_items"), ("payments", "fct_payments")):
        expected = conn.execute("SELECT count(DISTINCT natural_key) AS n FROM landing.source_versions WHERE entity=%s AND source_cut<=%s", (entity, cut)).fetchone()["n"]
        assert results[model] == expected, (entity, expected, results[model])
    checks = conn.execute("""SELECT
        (select sum(price) from work.stg_order_items)=(select sum(merchandise_value) from work.fct_order_items) AS items,
        (select sum(freight_value) from work.stg_order_items)=(select sum(freight_value) from work.fct_order_items) AS freight,
        (select sum(payment_value) from work.stg_payments)=(select sum(recorded_payment_value) from work.fct_payments) AS payments,
        (select count(distinct customer_unique_id)+2 from work.stg_customers)=(select count(*) from work.dim_customer) AS customers,
        not exists(select 1 from work.fct_orders where customer_key=0 or buyer_geography_key=0 or order_status_key=0) AS known_order_keys
        """).fetchone()
    assert all(checks.values()), checks
    warnings = conn.execute("""SELECT
      count(*) FILTER(WHERE NOT has_items) AS missing_items,
      count(*) FILTER(WHERE NOT has_payments) AS missing_payments,
      count(*) FILTER(WHERE missing_delivery_timestamp) AS missing_delivery_timestamp,
      count(*) FILTER(WHERE has_items AND has_payments AND abs(recorded_payment_total-item_merchandise_total-item_freight_total)>0.01) AS payment_delta,
      count(*) FILTER(WHERE temporal_anomaly) AS temporal_anomaly,
      (select count(*) from work.dim_product where product_key>0 and category_missing) AS missing_category
      FROM work.fct_orders""").fetchone()
    rules = {"missing_items": "DQ-COV-001", "missing_payments": "DQ-COV-002", "missing_category": "DQ-CAT-001",
             "missing_delivery_timestamp": "DQ-TIME-001", "payment_delta": "DQ-PAY-001", "temporal_anomaly": "DQ-TIME-002"}
    for reason, affected in warnings.items():
        if affected:
            identity = uuid5(NAMESPACE_URL, f"salesdw:{run_id}:{rules[reason]}")
            conn.execute("INSERT INTO ops.dq_issues(issue_id,pipeline_run_id,batch_id,rule_id,severity,reason_code,entity,scope_key,affected_records,redacted_details) VALUES(%s,%s,%s,%s,'warning',%s,'olist','source_cut',%s,%s) ON CONFLICT DO NOTHING",
                         (identity, run_id, ctx["batch_id"], rules[reason], reason, affected, Jsonb({"source_cut": cut, "policy": "preserve and explain source; no balancing"})))
    if results["fct_orders"] == 99441:
        assert {k: warnings[k] for k in ("missing_items", "missing_payments", "missing_category", "missing_delivery_timestamp", "payment_delta")} == {
            "missing_items": 775, "missing_payments": 1, "missing_category": 610, "missing_delivery_timestamp": 8, "payment_delta": 303}
    return {"rows": results, "money_and_identity_checks": checks, "source_warnings": warnings}
