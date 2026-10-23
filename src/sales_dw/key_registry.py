"""Allocate dimension SKs once under the current fenced transform owner."""
from .config import connect, context
from .leases import assert_owned


def ensure(run_id):
    cut = context(run_id)["source_cut"]
    with connect("transform") as conn:
        assert_owned(conn, run_id)
        sources = {
            "customer": ("customers", "payload->>'customer_unique_id'"),
            "product": ("products", "payload->>'product_id'"),
            "seller": ("sellers", "payload->>'seller_id'"),
            "buyer_geography": ("customers", "jsonb_build_array(payload->>'customer_zip_code_prefix',payload->>'customer_city',payload->>'customer_state')::text"),
            "order_status": ("orders", "payload->>'order_status'"),
            "payment_method": ("payments", "payload->>'payment_type'"),
        }
        counts = {}
        for namespace, (entity, expr) in sources.items():
            # expr comes only from the fixed mapping above, never from a user identifier.
            q = f"""INSERT INTO ops.dimension_key_registry(namespace,natural_key,version_identity,allocated_by_run)
              SELECT %s, nk,'snapshot',%s FROM (SELECT DISTINCT {expr} AS nk
                FROM (SELECT DISTINCT ON(entity,natural_key) payload FROM landing.source_versions
                      WHERE entity=ANY(%s) AND source_cut<=%s ORDER BY entity,natural_key,source_cut DESC) s) keys
              WHERE nk IS NOT NULL ORDER BY nk ON CONFLICT(namespace,natural_key,version_identity) DO NOTHING"""
            entities = [entity, "order_items"] if namespace == "product" else [entity]
            counts[namespace] = conn.execute(q, ("olist:" + namespace, run_id, entities, cut)).rowcount
    return counts
