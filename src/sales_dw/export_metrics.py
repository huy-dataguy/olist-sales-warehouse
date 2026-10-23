"""Compile AND execute local MetricFlow, compare every result to independent SQL."""
from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import re
import subprocess
import yaml

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from .config import ROOT, connect, context, run_dir
from .leases import assert_owned, renew
from .snapshot_release import check_result
from .transform import dbt_env, execute, tool
from .fault_injection import enabled, hit


def normalized(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def assert_forbidden_dimension(result):
    message = result.stdout + result.stderr
    if result.returncode == 0 or "during query resolution" not in message or "product__category" not in message:
        raise AssertionError("Expected a MetricFlow grouping-resolution rejection, not an unrelated execution error")


def assert_parity(actual, expected, keys, metrics):
    def keyed(rows):
        result = {tuple(normalized(r[k]) for k in keys): r for r in rows}
        if len(result) != len(rows):
            raise AssertionError("Duplicate metric grain")
        return result
    a, e = keyed(actual), keyed(expected)
    if set(a) != set(e):
        raise AssertionError(f"Metric group coverage differs: actual={len(a)}, expected={len(e)}")
    for key in a:
        for metric in metrics:
            x, y = a[key][metric], e[key][metric]
            if x is None or y is None:
                if x is not None or y is not None:
                    raise AssertionError((key, metric, x, y))
            elif metric in {"delivered_aov", "cancellation_rate"}:
                if abs(Decimal(str(x)) - Decimal(str(y))) > Decimal("0.000000001"):
                    raise AssertionError((key, metric, x, y))
            elif Decimal(str(x)) != Decimal(str(y)):
                raise AssertionError((key, metric, x, y))


def reference_query(export_id):
    """A separately authored SQL oracle; never joins atomic facts to each other."""
    grain = "day" if export_id == "sales_daily" else "month"
    extra = {"product_monthly": ("p.category", "category"), "seller_monthly": ("s.seller_id", "seller_id"), "buyer_state_monthly": ("g.state", "state")}.get(export_id)
    field = f",{extra[0]} AS {extra[1]}" if extra else ""
    group = f",{extra[0]}" if extra else ""
    item = f"""select date_trunc('{grain}',i.purchase_timestamp)::date as {grain}{field},
        sum(case when status.is_delivered then i.merchandise_value else 0 end) as delivered_merchandise_value,
        sum(case when status.is_delivered then i.item_row_count else 0 end) as delivered_item_rows
      from semantic_input.fct_order_items i
      join semantic_input.dim_order_status status using(release_id,order_status_key)
      join semantic_input.dim_product p using(release_id,product_key)
      join semantic_input.dim_seller s using(release_id,seller_key)
      join semantic_input.dim_buyer_geography g using(release_id,buyer_geography_key)
      group by date_trunc('{grain}',i.purchase_timestamp)::date{group}"""
    if export_id in {"product_monthly", "seller_monthly"}:
        return item
    order_extra = ",g.state AS state" if extra else ""
    order_group = ",g.state" if extra else ""
    orders = f"""select date_trunc('{grain}',o.purchase_timestamp)::date as {grain}{order_extra},
        sum(order_count) as total_orders,sum(delivered_order_count) as delivered_orders,sum(canceled_order_count) as canceled_orders,
        count(distinct customer_key) filter(where delivered_order_count=1 and customer_key>0) as delivered_unique_customers
      from semantic_input.fct_orders o join semantic_input.dim_buyer_geography g using(release_id,buyer_geography_key)
      group by date_trunc('{grain}',o.purchase_timestamp)::date{order_group}"""
    join_keys = grain + (",state" if extra else "")
    return f"""with orders as ({orders}),items as ({item})
      select {grain}{',state' if extra else ''},total_orders,delivered_orders,canceled_orders,
      canceled_orders::numeric/nullif(total_orders,0) as cancellation_rate,
      coalesce(delivered_merchandise_value,0) as delivered_merchandise_value,
      coalesce(delivered_merchandise_value,0)/nullif(delivered_orders,0) as delivered_aov,
      delivered_unique_customers,coalesce(delivered_item_rows,0) as delivered_item_rows
      from orders left join items using({join_keys})"""


def export(run_id):
    renew(run_id)
    ctx = context(run_id)
    rid = ctx["release_id"]
    # A worker can die after committing all five exports but before recording
    # metrics_validated. Recover the committed immutable outputs, never insert
    # them again or silently replace a manifest with a new parse invocation.
    recovered = recover_committed_exports(run_id)
    if recovered is not None:
        return recovered
    target = run_dir(run_id) / "semantic"
    target.mkdir(exist_ok=True)
    # dbt-metricflow 0.15 hardcodes <project>/target/semantic_manifest.json.
    # Give each run its own project root; never mutate the read-only source project.
    project = run_dir(run_id) / "semantic-project"
    project.mkdir(exist_ok=True)
    definition = yaml.safe_load((ROOT / "dbt/semantic/dbt_project.yml").read_text())
    definition["model-paths"] = [str(ROOT / "dbt/models/semantic_input"), str(ROOT / "dbt/models/semantic")]
    definition["target-path"] = "target"
    (project / "dbt_project.yml").write_text(yaml.safe_dump(definition))
    if not (project / "target").exists():
        (project / "target").symlink_to(target, target_is_directory=True)
    env = dbt_env("semantic", "semantic_input", rid)
    env.update(DBT_PROFILES_DIR=str(ROOT / "dbt"), DBT_TARGET_PATH=str(target), SALES_SEMANTIC_TARGET=str(target), DBT_LOG_PATH=str(target / "logs"), NO_COLOR="1")
    execute([tool("dbt"), "parse", "--project-dir", str(project), "--profiles-dir", str(ROOT / "dbt"), "--target-path", str(target), "--log-path", str(target / "logs")], cwd=project, env=env, log=target / "parse.log")
    manifest = target / "semantic_manifest.json"
    manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    catalog = json.loads((ROOT / "contracts/metric-catalog.json").read_text())
    reports = {}
    with connect("semantic", release_id=rid) as conn:
        assert_owned(conn, run_id)
        binding = conn.execute("SELECT ops.bound_release_id() AS id").fetchone()["id"]
        assert str(binding) == rid
        for spec in catalog["exports"]:
            name = spec["id"]
            grain = "day" if name == "sales_daily" else "month"
            dims = [f"metric_time__{grain}"]
            rename = {dims[0]: grain}
            if name in {"product_monthly", "seller_monthly", "buyer_state_monthly"}:
                dim = {"product_monthly": "product__category", "seller_monthly": "seller__seller_id", "buyer_state_monthly": "buyer_geography__state"}[name]
                dims.append(dim)
                rename[dim] = dim.split("__")[-1]
            base = [tool("mf"), "query", "--metrics", ",".join(spec["metrics"]), "--group-by", ",".join(dims)]
            explanation = target / (name + "-explain.log")
            execute([*base, "--explain"], cwd=project, env=env, log=explanation)
            output = explanation.read_text()
            match = re.search(r"(?m)^(?:WITH|SELECT)\b", output)
            if not match:
                raise RuntimeError("No generated MetricFlow SQL in " + str(explanation))
            generated = output[match.start():].strip()
            (target / (name + ".sql")).write_text(generated + "\n")
            # No SQL rewriting: execute exactly what MetricFlow generated, with a bound connection.
            conn.execute("EXPLAIN (FORMAT JSON) " + generated).fetchall()
            rows = [{rename.get(k, k): v for k, v in r.items()} for r in conn.execute(generated)]
            oracle = conn.execute(reference_query(name)).fetchall()
            keys = [k for k in spec["grain"] if k != "release_id"]
            if name == "sales_monthly" and enabled("parity_result"):
                rows[0]["total_orders"] += 1  # Deliberate fixture; oracle must catch it.
            assert_parity(rows, oracle, keys, spec["metrics"])
            native = target / (name + ".csv")
            execute([*base, "--csv", str(native), "--quiet"], cwd=project, env=env, log=target / (name + "-execution.log"))
            # This second path proves that the native MetricFlow adapter receives PGOPTIONS too.
            native_rows = []
            with native.open() as stream:
                for record in csv.DictReader(stream):
                    mapped = {rename.get(k, k): v for k, v in record.items()}
                    for k in keys:
                        if k in {"day", "month"}:
                            mapped[k] = mapped[k][:10]
                    for metric in spec["metrics"]:
                        mapped[metric] = Decimal(mapped[metric]) if mapped[metric] not in {"", "None", "null"} else None
                    native_rows.append(mapped)
            assert_parity(native_rows, rows, keys, spec["metrics"])
            sha = hashlib.sha256(generated.encode()).hexdigest()
            columns = ["release_id", *keys, *spec["metrics"], "generated_sql_sha256"]
            insert = sql.SQL("INSERT INTO reporting.{} ({}) VALUES ({})").format(sql.Identifier(name), sql.SQL(",").join(map(sql.Identifier, columns)), sql.SQL(",").join([sql.Placeholder()] * len(columns)))
            with conn.cursor() as cur:
                cur.executemany(insert, [[rid, *[normalized(r[k]) for k in keys], *[r[m] for m in spec["metrics"]], sha] for r in rows])
            content_sha = hashlib.sha256(json.dumps(sorted(rows, key=lambda r: tuple(str(r[k]) for k in keys)), sort_keys=True, default=str).encode()).hexdigest()
            conn.execute("INSERT INTO ops.export_queries(release_id,export_id,semantic_manifest_sha256,generated_sql_sha256,generated_sql,query_parameters,result_row_count,logical_result_sha256) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                         (rid, name, manifest_sha, sha, generated, Jsonb({"metrics": spec["metrics"], "group_by": dims}), len(rows), content_sha))
            reports[name] = {"rows": len(rows), "parity": True, "native_adapter_parity": True, "sql_sha256": sha}
            hit("semantic.after." + name)
    hit("semantic.after_commit")
    # Wrong or absent release binding must be rejected by actual PostgreSQL.
    for invalid in (None, "00000000-0000-0000-0000-000000000001"):
        try:
            with connect("semantic", release_id=invalid) as conn:
                conn.execute("SELECT * FROM semantic_input.metric_orders LIMIT 1").fetchall()
        except psycopg.Error:
            pass
        else:
            raise AssertionError("Invalid semantic binding was accepted")
    forbidden = subprocess.run([tool("mf"), "query", "--metrics", "delivered_orders", "--group-by", "product__category", "--explain"], cwd=project, env=env, capture_output=True, text=True, timeout=90)
    (target / "forbidden-dimension.log").write_text(forbidden.stdout + forbidden.stderr)
    assert_forbidden_dimension(forbidden)
    with connect("snapshot") as conn:
        assert_owned(conn, run_id)
        conn.execute("UPDATE ops.releases SET semantic_manifest_sha256=%s,state='metrics_validated' WHERE release_id=%s AND state='snapshotted'", (manifest_sha, rid))
        for check in ("V-005", "V-017"):
            check_result(conn, rid, check, f"var/runs/{run_id}/semantic.json")
    return {"release_id": rid, "exports": reports, "invalid_bindings_rejected": True, "forbidden_dimension_rejected": True}


def recover_committed_exports(run_id):
    """Reconcile a lost acknowledgement with durable content and native output."""
    ctx = context(run_id)
    rid = ctx["release_id"]
    catalog = json.loads((ROOT / "contracts/metric-catalog.json").read_text())
    with connect("semantic", release_id=rid) as conn:
        assert_owned(conn, run_id)
        recorded = {r["export_id"]: r for r in conn.execute("SELECT * FROM ops.export_queries WHERE release_id=%s", (rid,))}
        if not recorded:
            return None
        if set(recorded) != {s["id"] for s in catalog["exports"]}:
            raise RuntimeError("Partial committed export set; do not repair in place")
        manifests = {r["semantic_manifest_sha256"] for r in recorded.values()}
        manifest = run_dir(run_id) / "semantic/semantic_manifest.json"
        if len(manifests) != 1 or not manifest.exists() or hashlib.sha256(manifest.read_bytes()).hexdigest() not in manifests:
            raise RuntimeError("Committed exports lost their original semantic manifest")
        reports = {}
        for spec in catalog["exports"]:
            name = spec["id"]
            saved = recorded[name]
            keys = [k for k in spec["grain"] if k != "release_id"]
            columns = keys + spec["metrics"]
            rows = conn.execute(sql.SQL("SELECT {} FROM reporting.{} WHERE release_id=%s").format(sql.SQL(",").join(map(sql.Identifier, columns)), sql.Identifier(name)), (rid,)).fetchall()
            assert len(rows) == saved["result_row_count"]
            assert hashlib.sha256(saved["generated_sql"].encode()).hexdigest() == saved["generated_sql_sha256"]
            aliases = {name: name.split("__")[-1] for name in saved["query_parameters"]["group_by"]}
            original_shape = [{aliases.get(k, k): v for k, v in row.items()} for row in conn.execute(saved["generated_sql"])]
            digest = hashlib.sha256(json.dumps(sorted(original_shape, key=lambda r: tuple(str(r[k]) for k in keys)), sort_keys=True, default=str).encode()).hexdigest()
            assert digest == saved["logical_result_sha256"], "Committed query result changed"
            assert_parity(rows, original_shape, keys, spec["metrics"])
            assert_parity(rows, conn.execute(reference_query(name)).fetchall(), keys, spec["metrics"])
            reports[name] = {"rows": len(rows), "parity": True, "committed_content_verified": True}
    # The original export transaction commits only after all native adapter
    # executions pass. Recheck connection and join restrictions on recovery.
    for invalid in (None, "00000000-0000-0000-0000-000000000001"):
        try:
            with connect("semantic", release_id=invalid) as conn:
                conn.execute("SELECT * FROM semantic_input.metric_orders LIMIT 1").fetchall()
        except psycopg.Error:
            pass
        else:
            raise AssertionError("Invalid semantic binding was accepted")
    project = run_dir(run_id) / "semantic-project"
    env = dbt_env("semantic", "semantic_input", rid)
    env.update(DBT_PROFILES_DIR=str(ROOT / "dbt"), DBT_LOG_PATH=str(run_dir(run_id) / "semantic/logs"), NO_COLOR="1")
    rejected = subprocess.run([tool("mf"), "query", "--metrics", "delivered_orders", "--group-by", "product__category", "--explain"], cwd=project, env=env, capture_output=True, text=True, timeout=90)
    (run_dir(run_id) / "semantic/forbidden-dimension.log").write_text(rejected.stdout + rejected.stderr)
    assert_forbidden_dimension(rejected)
    with connect("snapshot") as conn:
        assert_owned(conn, run_id)
        state = conn.execute("SELECT state FROM ops.releases WHERE release_id=%s FOR UPDATE", (rid,)).fetchone()["state"]
        if state not in {"snapshotted", "metrics_validated", "published"}:
            raise RuntimeError("Cannot recover a terminal failed candidate")
        conn.execute("UPDATE ops.releases SET semantic_manifest_sha256=%s,state='metrics_validated' WHERE release_id=%s AND state='snapshotted'", (next(iter(manifests)), rid))
        for check in ("V-005", "V-017"):
            check_result(conn, rid, check, f"var/runs/{run_id}/semantic.json")
    return {"release_id": rid, "exports": reports, "recovered_commit": True, "invalid_bindings_rejected": True, "forbidden_dimension_rejected": True}
