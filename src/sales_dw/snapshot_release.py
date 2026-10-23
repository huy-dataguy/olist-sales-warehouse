"""Freeze all consumer relations under one fenced repeatable-read transaction."""
import json
from uuid import uuid5, NAMESPACE_URL

from psycopg import sql

from .config import connect, context, save_context, run_dir
from .leases import assert_owned, renew
from .quality import MODELS, check_work, logical_hash
from .fault_injection import hit


def check_result(conn, release_id, check_id, evidence):
    conn.execute("INSERT INTO ops.check_results(release_id,check_id,state,evidence_uri) VALUES(%s,%s,'passed',%s) ON CONFLICT(release_id,check_id) DO NOTHING", (release_id, check_id, evidence))


def snapshot(run_id):
    renew(run_id)
    ctx = context(run_id)
    rid = str(uuid5(NAMESPACE_URL, "salesdw:release:" + str(run_id)))
    save_context(run_id, release_id=rid)
    with connect("snapshot") as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        conn.execute("SET LOCAL work_mem='32MB'")
        assert_owned(conn, run_id)
        existing = conn.execute("SELECT state FROM ops.releases WHERE release_id=%s", (rid,)).fetchone()
        if existing:
            if existing["state"] not in {"snapshotted", "metrics_validated", "published"}:
                raise RuntimeError("A failed/incomplete candidate cannot be reset")
            return {"release_id": rid, "state": existing["state"], "retry": "existing immutable snapshot"}
        quality = check_work(conn, run_id)
        conn.execute("INSERT INTO ops.releases(release_id,pipeline_run_id,source_cut,contract_version,model_version,fencing_token,state) VALUES(%s,%s,%s,'2.0.0','2.0.0',%s,'building')", (rid, run_id, ctx["source_cut"], ctx["fencing_token"]))
        conn.execute("UPDATE ops.releases SET state='warehouse_validated' WHERE release_id=%s", (rid,))
        metadata = {}
        for model, key in MODELS.items():
            columns = [r["column_name"] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='warehouse_store' AND table_name=%s ORDER BY ordinal_position", (model,))]
            expressions = [sql.Placeholder() if c in {"release_id", "source_cut"} else sql.Identifier(c) for c in columns]
            params = [rid if c == "release_id" else ctx["source_cut"] for c in columns if c in {"release_id", "source_cut"}]
            statement = sql.SQL("INSERT INTO warehouse_store.{} ({}) SELECT {} FROM work.{}").format(
                sql.Identifier(model), sql.SQL(",").join(map(sql.Identifier, columns)), sql.SQL(",").join(expressions), sql.Identifier(model))
            # A real no-write plan precedes the bulk DML copy.
            conn.execute(sql.SQL("EXPLAIN (FORMAT JSON) ") + statement, params).fetchall()
            count = conn.execute(statement, params).rowcount
            conn.execute(sql.SQL("ANALYZE warehouse_store.{}").format(sql.Identifier(model)))
            # Hash only this immutable release, not all retained snapshots.
            before = logical_hash(conn, "work", model)
            after = conn.execute(sql.SQL("""SELECT count(*) AS n,encode(sha256(convert_to(coalesce(string_agg(md5((to_jsonb(s)-ARRAY['release_id','source_cut','created_run_id','last_changed_run_id'])::text),'' ORDER BY {}),''),'UTF8')),'hex') AS sha
              FROM warehouse_store.{} s WHERE release_id=%s""").format(sql.Identifier(key), sql.Identifier(model)), (rid,)).fetchone()
            assert before == after and count == before["n"], (model, before, after, count)
            conn.execute("INSERT INTO ops.snapshot_relations(release_id,model_name,row_count,logical_content_sha256,validated) VALUES(%s,%s,%s,%s,true)", (rid, model, count, after["sha"]))
            metadata[model] = {"rows": count, "logical_sha256": after["sha"]}
            hit("snapshot.after." + model)
            conn.execute(sql.SQL("INSERT INTO ops.lineage_edges(release_id,model_name,derived_natural_key,source_version_id,input_role) SELECT release_id,%s,{}::text,lineage_id,'primary_source' FROM warehouse_store.{} WHERE release_id=%s AND lineage_id IS NOT NULL").format(sql.Identifier(key), sql.Identifier(model)), (model, rid))
        # Add parent-order and customer-reference inputs for every transactional child.
        for model, key in (("fct_orders", "order_key"), ("fct_order_items", "order_item_key"), ("fct_payments", "payment_key")):
            conn.execute(sql.SQL("""INSERT INTO ops.lineage_edges
              SELECT f.release_id,%s,f.{}::text,o.lineage_id,'parent_order' FROM warehouse_store.{} f
              JOIN warehouse_store.fct_orders o ON o.release_id=f.release_id AND o.source_system=f.source_system AND o.order_id=f.order_id
              WHERE f.release_id=%s ON CONFLICT DO NOTHING""").format(sql.Identifier(key), sql.Identifier(model)), (model, rid))
            conn.execute(sql.SQL("""INSERT INTO ops.lineage_edges
              SELECT f.release_id,%s,f.{}::text,c.lineage_id,'customer_reference' FROM warehouse_store.{} f
              JOIN warehouse_store.fct_orders o ON o.release_id=f.release_id AND o.source_system=f.source_system AND o.order_id=f.order_id
              JOIN work.stg_customers c ON c.customer_id=o.source_customer_id
              WHERE f.release_id=%s ON CONFLICT DO NOTHING""").format(sql.Identifier(key), sql.Identifier(model)), (model, rid))
        for input_name, dim, fk, input_key in (("product", "dim_product", "product_key", "product_key"), ("seller", "dim_seller", "seller_key", "seller_key")):
            conn.execute(sql.SQL("""INSERT INTO ops.lineage_edges
              SELECT f.release_id,'fct_order_items',f.order_item_key,d.lineage_id,%s
              FROM warehouse_store.fct_order_items f JOIN warehouse_store.{} d USING(release_id,{})
              WHERE f.release_id=%s AND d.lineage_id IS NOT NULL ON CONFLICT DO NOTHING""").format(sql.Identifier(dim), sql.Identifier(fk)), (input_name, rid))
        for check in ("V-004", "V-007", "V-013"):
            check_result(conn, rid, check, f"var/runs/{run_id}/snapshot.json")
        conn.execute("UPDATE ops.releases SET state='snapshotted' WHERE release_id=%s", (rid,))
        conn.execute("INSERT INTO ops.state_events(pipeline_run_id,release_id,actor_role,previous_state,new_state,reason,fencing_token) VALUES(%s,%s,current_user,'warehouse_validated','snapshotted','Consistent 10-model copy; constraints and logical hashes checked',%s)", (run_id, rid, ctx["fencing_token"]))
    return {"release_id": rid, "quality": quality, "snapshot_relations": metadata}
