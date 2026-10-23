"""Independently check source contracts and Kimball golden design expectations.

This does not run a Warehouse, production transformations or Airflow.
"""

import argparse
import collections
import csv
from datetime import datetime
from decimal import Decimal
import io
import json
from pathlib import Path
import zipfile

from jsonschema import Draft202012Validator, FormatChecker
from pglast import parse_sql, ast
from pglast.enums import ConstrType


ROOT = Path(__file__).resolve().parents[1]
FORMATS = FormatChecker()


@FORMATS.checks("olist-timestamp", raises=ValueError)
def source_timestamp(value):
    if not isinstance(value, str):
        return False
    datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return True


def read_json(path):
    return json.loads((ROOT / path).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, help="Validate every selected real-source CSV row when supplied")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evidence/design-contracts.json")
    args = parser.parse_args()
    checks, source_reports = [], []

    def check(name, actual, expected=True):
        passed = actual == expected
        checks.append({"check": name, "passed": passed, "actual": actual, "expected": expected})
        if not passed:
            print(f"FAIL: {name}", flush=True)

    schemas = {}
    for path in sorted((ROOT / "contracts").rglob("*.schema.json")):
        schema = json.loads(path.read_text())
        Draft202012Validator.check_schema(schema)
        schemas[path.relative_to(ROOT).as_posix()] = Draft202012Validator(schema, format_checker=FORMATS)
    check("json_schemas_are_valid", len(schemas), 10)
    ddl = (ROOT / "db/design/001_warehouse_schema.sql").read_text()
    statements = parse_sql(ddl)
    check("physical_ddl_parses_as_postgresql_without_execution", len(statements) > 50)
    check("physical_ddl_has_no_fact_to_fact_foreign_key", "REFERENCES warehouse_store.fct_" not in ddl)
    check("bi_views_exclude_unpublished_candidates", "WHERE r.state IN ('metrics_validated','published')" not in ddl)
    warehouse = read_json("contracts/warehouse-model.json")
    metrics = read_json("contracts/metric-catalog.json")
    dimensions = {dim["name"]: dim for dim in warehouse["dimensions"]}
    facts = {fact["name"]: fact for fact in warehouse["facts"]}
    tables = {s.stmt.relation.relname: s.stmt for s in statements if isinstance(s.stmt, ast.CreateStmt)}
    for dim in dimensions.values():
        table = tables[dim["name"]]
        columns = {col.colname: col for col in table.tableElts if isinstance(col, ast.ColumnDef)}
        key_type = columns[dim["primary_key"]].typeName.names[-1].sval
        check(f"{dim['name']}_physical_integer_key", key_type, "int4" if dim["name"] == "dim_date" else "int8")
        primary_keys = [[col.sval for col in constraint.keys] for constraint in table.tableElts if isinstance(constraint, ast.Constraint) and constraint.contype == ConstrType.CONSTR_PRIMARY]
        check(f"{dim['name']}_physical_release_pk", primary_keys, [dim["consumer_unique_key"]])
    for fact in facts.values():
        table = tables[fact["name"]]
        unique_keys = [[col.sval for col in constraint.keys] for constraint in table.tableElts if isinstance(constraint, ast.Constraint) and constraint.contype == ConstrType.CONSTR_UNIQUE]
        check(f"{fact['name']}_physical_grain", fact["consumer_unique_key"] in unique_keys)
        physical_fks = {tuple(col.sval for col in constraint.fk_attrs): (constraint.pktable.schemaname, constraint.pktable.relname, tuple(col.sval for col in constraint.pk_attrs))
                        for constraint in table.tableElts if isinstance(constraint, ast.Constraint) and constraint.contype == ConstrType.CONSTR_FOREIGN}
        for key, target in fact["foreign_keys"].items():
            target_table, target_key = target.split(".")
            check(f"{fact['name']}_{key}_physical_release_fk", physical_fks.get(("release_id", key)), ("warehouse_store", target_table, ("release_id", target_key)))
    check("product_type2_physical_exclusion_declared", any(isinstance(c, ast.Constraint) and c.contype == ConstrType.CONSTR_EXCLUSION for c in tables["dim_product"].tableElts))
    check("bus_has_seven_conformed_dimensions", len(dimensions), 7)
    check("bus_has_three_business_processes", len(facts), 3)
    check("no_atomic_fact_to_fact_reporting", warehouse["reporting_rules"]["fact_to_fact_atomic_joins"], False)
    for fact in facts.values():
        for fk, ref in fact["foreign_keys"].items():
            table, column = ref.split(".")
            check(f"{fact['name']}.{fk}_conforms", table in dimensions and dimensions[table]["primary_key"] == column)
        check(f"{fact['name']}_release_in_unique_key", fact["consumer_unique_key"][0], "release_id")
    check("customer_dimension_has_no_current_address", not any(x in dimensions["dim_customer"]["attributes"] for x in ("state", "city", "postal_prefix")))
    for dim in dimensions.values():
        check(f"{dim['name']}_unknown_member", dim["reserved_members"]["0"], "unknown")
    by_metric = {m["name"]: m for m in metrics["metrics"]}
    check("metric_names_unique", len(by_metric), len(metrics["metrics"]))
    for name in ("delivered_orders", "delivered_aov", "delivered_unique_customers"):
        check(f"{name}_has_no_product_or_seller_fanout", not any(d.startswith(("product__", "seller__")) for d in by_metric[name]["allowed_dimensions"]))
    for metric in metrics["metrics"]:
        for component in metric["components"] or []:
            check(f"{metric['name']}_component_{component}", component in by_metric)
    check("distinct_customers_declared_nonadditive", by_metric["delivered_unique_customers"]["additivity"], "non_additive_distinct")

    catalog = read_json("contracts/source-catalog.json")
    if args.source:
        with zipfile.ZipFile(args.source) as archive:
            for feed in catalog["feeds"]:
                validator = schemas[feed["schema"]]
                keys, duplicates, count, error_count, errors = set(), 0, 0, 0, []
                with archive.open(feed["file_member"]) as raw:
                    reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"))
                    header_ok = set(reader.fieldnames) == set(validator.schema["required"])
                    for row in reader:
                        count += 1
                        for error in validator.iter_errors(row):
                            error_count += 1
                            if len(errors) < 10:
                                errors.append({"row": count, "field": list(error.path), "validator": error.validator})
                        key = tuple(row[k] for k in feed["natural_key"])
                        if key in keys:
                            duplicates += 1
                        keys.add(key)
                source_reports.append({"entity": feed["entity"], "rows": count, "headers_match": header_ok,
                                       "duplicate_natural_keys": duplicates, "contract_error_count": error_count, "sample_contract_errors": errors})
                check(f"source_{feed['entity']}_contract", header_ok and not errors and duplicates == 0)
                print(f"source {feed['entity']}: {count} rows, {len(errors)} sampled contract errors", flush=True)
        customer_schema = schemas["contracts/source/customers.schema.json"]
        example = {"customer_id": "a" * 32, "customer_unique_id": "b" * 32,
                   "customer_zip_code_prefix": "01001", "customer_city": "demo", "customer_state": "SP"}
        check("source_contract_accepts_leading_zero_postal_prefix", customer_schema.is_valid(example))
        check("source_contract_rejects_blank_key", customer_schema.is_valid({**example, "customer_id": ""}), False)
        check("source_contract_rejects_schema_drift", customer_schema.is_valid({**example, "unexpected": "x"}), False)

    data = read_json("tests/fixtures/kimball/input.json")
    check("golden_fixture_schema", schemas["contracts/kimball-fixture.schema.json"].is_valid(data))
    expected = read_json("tests/fixtures/kimball/expected.json")
    check("golden_fixture_namespace_is_synthetic", data["metadata"]["source_system"], "synthetic_contract_fixture")
    customers = {r["customer_id"]: r for r in data["customers"]}
    orders = {r["order_id"]: r for r in data["orders"]}
    products = {r["product_id"]: r for r in data["products"]}
    check("golden_order_grain", len(orders), len(data["orders"]))
    check("golden_item_grain", len({(r['order_id'], r['order_item_id']) for r in data['items']}), len(data['items']))
    check("golden_payment_grain", len({(r['order_id'], r['payment_sequential']) for r in data['payments']}), len(data['payments']))
    check("golden_fact_references_resolve", all(r["order_id"] in orders for r in data["items"] + data["payments"]))

    def aggregate(order_rows):
        selected = {r["order_id"] for r in order_rows}
        delivered = {k for k in selected if orders[k]["status"] == "delivered"}
        rows = [r for r in data["items"] if r["order_id"] in delivered]
        value = sum((Decimal(r["price"]) for r in rows), Decimal())
        return {"total_orders": len(selected), "delivered_orders": len(delivered),
                "canceled_orders": sum(orders[k]["status"] == "canceled" for k in selected),
                "delivered_merchandise_value": f"{value:.2f}",
                "delivered_unique_customers": len({customers[orders[k]["customer_id"]]["customer_unique_id"] for k in delivered}),
                "delivered_item_rows": len(rows)}

    totals = aggregate(data["orders"])
    totals["delivered_aov"] = f"{Decimal(totals['delivered_merchandise_value']) / totals['delivered_orders']:.2f}"
    check("golden_total_metrics", totals, expected["totals"])
    for month, month_expected in expected["monthly"].items():
        check(f"golden_month_{month}", aggregate([r for r in data["orders"] if r["purchased_at"].startswith(month)]), month_expected)
    group_values = {name: collections.defaultdict(Decimal) for name in ("category", "seller", "buyer_state")}
    for row in data["items"]:
        order = orders[row["order_id"]]
        if order["status"] != "delivered":
            continue
        group_values["category"][products[row["product_id"]]["category"] or "Unknown"] += Decimal(row["price"])
        group_values["seller"][row["seller_id"]] += Decimal(row["price"])
        group_values["buyer_state"][customers[order["customer_id"]]["state"]] += Decimal(row["price"])
    for group, values in group_values.items():
        check(f"golden_{group}_additivity", {key: f"{value:.2f}" for key, value in values.items()}, expected[group + "_value"])
    state_customers = collections.defaultdict(set)
    for order in data["orders"]:
        if order["status"] == "delivered":
            customer = customers[order["customer_id"]]
            state_customers[customer["state"]].add(customer["customer_unique_id"])
    state_counts = {key: len(value) for key, value in state_customers.items()}
    check("golden_state_distincts", state_counts, expected["buyer_state_customers"])
    check("state_distincts_must_not_be_summed", sum(state_counts.values()) != totals["delivered_unique_customers"])
    daily = {r["purchased_at"][:10] for r in data["orders"]}
    daily_rows = [aggregate([r for r in data["orders"] if r["purchased_at"].startswith(day)]) for day in daily]
    daily_customers = sum(r["delivered_unique_customers"] for r in daily_rows)
    check("daily_distincts_must_not_be_summed", daily_customers != totals["delivered_unique_customers"])
    daily_aovs = [Decimal(r["delivered_merchandise_value"]) / r["delivered_orders"] for r in daily_rows if r["delivered_orders"]]
    check("daily_aovs_must_not_be_averaged", sum(daily_aovs) / len(daily_aovs) != Decimal(totals["delivered_aov"]))
    computed_ratios = {
        "overall_aov": Decimal(totals["delivered_merchandise_value"]) / totals["delivered_orders"],
        "overall_cancellation_rate": Decimal(totals["canceled_orders"]) / totals["total_orders"],
        "incorrect_average_daily_aov": sum(daily_aovs) / len(daily_aovs),
    }
    for month in expected["monthly"]:
        values = aggregate([r for r in data["orders"] if r["purchased_at"].startswith(month)])
        computed_ratios[month + "_aov"] = Decimal(values["delivered_merchandise_value"]) / values["delivered_orders"]
        computed_ratios[month + "_cancellation_rate"] = Decimal(values["canceled_orders"]) / values["total_orders"]
    for name, expected_ratio in expected["ratios"].items():
        check("golden_ratio_" + name, abs(computed_ratios[name] - Decimal(expected_ratio)) <= Decimal("1e-15"))

    by_items, by_payments = collections.defaultdict(list), collections.defaultdict(list)
    for row in data["items"]:
        by_items[row["order_id"]].append(row)
    for row in data["payments"]:
        by_payments[row["order_id"]].append(row)
    quality = {"orders_without_items": sum(k not in by_items for k in orders),
               "orders_without_payments": sum(k not in by_payments for k in orders),
               "delivered_orders_without_delivery_timestamp": sum(r["status"] == "delivered" and not r["delivered_at"] for r in orders.values()),
               "products_without_category": sum(r["category"] is None for r in products.values()),
               "payment_difference_above_one_cent": 0, "delivery_eligible_orders": 0, "on_time_delivery_orders": 0}
    for key in by_items.keys() & by_payments.keys():
        due = sum((Decimal(r["price"]) + Decimal(r["freight_value"]) for r in by_items[key]), Decimal())
        paid = sum((Decimal(r["payment_value"]) for r in by_payments[key]), Decimal())
        quality["payment_difference_above_one_cent"] += abs(paid - due) > Decimal("0.01")
    for row in orders.values():
        if row["status"] == "delivered" and row["delivered_at"] and row["estimated_delivery_at"]:
            delivered = datetime.fromisoformat(row["delivered_at"])
            purchase = datetime.fromisoformat(row["purchased_at"])
            if delivered >= purchase:
                quality["delivery_eligible_orders"] += 1
                quality["on_time_delivery_orders"] += delivered.date() <= datetime.fromisoformat(row["estimated_delivery_at"]).date()
    check("golden_quality_and_role_dates", quality, expected["quality"])
    unknown_delivery_key = 0 if orders["o4"]["delivered_at"] is None else int(orders["o4"]["delivered_at"][:10].replace("-", ""))
    check("missing_delivery_is_unknown_date_not_dropped_order", unknown_delivery_key, 0)
    fanout = expected["fanout"]
    key = fanout["order_id"]
    correct_items = sum((Decimal(r["price"]) for r in by_items[key]), Decimal())
    correct_payments = sum((Decimal(r["payment_value"]) for r in by_payments[key]), Decimal())
    for label, value in {"correct_merchandise": correct_items, "naive_join_merchandise": correct_items * len(by_payments[key]),
                         "correct_payment": correct_payments, "naive_join_payment": correct_payments * len(by_items[key])}.items():
        check("golden_" + label, f"{value:.2f}", fanout[label])
    empty_delivered_period = aggregate([orders["o5"]])
    denominator = empty_delivered_period["delivered_orders"]
    empty_period_aov = Decimal(empty_delivered_period["delivered_merchandise_value"]) / denominator if denominator else None
    check("zero_denominator_returns_null", empty_period_aov, expected["zero_denominator_result"])

    unique_changes = {}
    for row in data["scd2_arrivals"]:
        identity = (row["product_id"], row["valid_from"])
        if identity in unique_changes and unique_changes[identity]["category"] != row["category"]:
            raise ValueError("Conflicting fixture changes at the same effective time")
        unique_changes[identity] = row
    retained = []
    for row in sorted(unique_changes.values(), key=lambda r: (r["product_id"], r["valid_from"])):
        if retained and retained[-1]["product_id"] == row["product_id"] and retained[-1]["category"] == row["category"]:
            continue
        retained.append(row)
    versions = [{"surrogate_key": row["allocated_key"], "valid_from": row["valid_from"],
                 "valid_to": retained[i + 1]["valid_from"] if i + 1 < len(retained) else None,
                 "category": row["category"], "is_current": i == len(retained) - 1} for i, row in enumerate(retained)]
    check("scd2_late_arrival_and_repeat_payload", versions, expected["scd2_versions"])
    lookup_keys = []
    for at in data["scd2_lookups"]:
        found = [r for r in versions if r["valid_from"] <= at and (r["valid_to"] is None or at < r["valid_to"])]
        check("scd2_lookup_cardinality_" + at, len(found) <= 1)
        lookup_keys.append(found[0]["surrogate_key"] if found else 0)
    check("scd2_exact_boundaries_and_unknown_history", lookup_keys, expected["scd2_lookup_keys"])
    member = {"surrogate_key": data["inferred_member"]["allocated_key"], **data["inferred_member"]["initial"]}
    member.update(data["inferred_member"]["arriving"])
    check("inferred_member_keeps_surrogate_key", member["surrogate_key"], expected["inferred_member_key_after_enrichment"])
    check("inferred_member_enriched", member["is_inferred"], False)

    batch_validator = schemas["contracts/source-batch.schema.json"]
    unmarked_batch = {"source_system": "synthetic_contract_fixture", "source_version": "fixture-v1", "artifact_sha256": "0" * 64,
                      "batch_id": "fixture", "replay_plan_id": "golden-v1", "batch_sequence": 1, "schema_version": "1.0.0", "received_at_utc": "2024-01-01T00:00:00Z",
                      "scenario_id": None, "members": [{"entity": "orders", "file_member": "fixture.json", "row_count": 7}]}
    check("synthetic_batch_requires_scenario_label", batch_validator.is_valid(unmarked_batch), False)
    check("marked_synthetic_batch_is_valid", batch_validator.is_valid({**unmarked_batch, "scenario_id": "kimball-golden-v1"}))
    release_validator = schemas["contracts/release.schema.json"]
    published = {"release_id": "00000000-0000-4000-8000-000000000001", "source_cut": 1, "source_artifact_hashes": ["0" * 64],
                 "contract_version": "2.0.0", "model_version": "fixture-v1", "semantic_manifest_sha256": "0" * 64,
                 "fencing_token": 1, "state": "published", "checks": [{"id": ref, "status": "passed", "evidence": "fixture-only"} for ref in release_validator.schema["x-required-publish-checks"]],
                 "warehouse_snapshot": {"relation_count": 10, "relation_ids": list(dimensions) + list(facts), "row_count": 100, "validated": True},
                 "metric_exports": {"export_count": 5, "export_ids": [r["id"] for r in metrics["exports"]], "parity_passed": True}}
    check("published_release_contract_accepts_valid_fixture", release_validator.is_valid(published))
    bad_release = {**published, "metric_exports": {**published["metric_exports"], "parity_passed": False}}
    check("published_release_contract_rejects_failed_parity", release_validator.is_valid(bad_release), False)
    bad_release = {**published, "checks": [{**row, "status": "pending"} if row["id"] == "V-004" else row for row in published["checks"]]}
    check("published_release_contract_rejects_pending_checks", release_validator.is_valid(bad_release), False)
    bad_release = {**published, "checks": published["checks"][:-1]}
    check("published_release_contract_requires_all_mandatory_checks", release_validator.is_valid(bad_release), False)

    evidence = {"scope": "Design contracts, real-source row schema checks when requested, independent synthetic Kimball expectations. No database, production transformation or service execution.",
                "source_row_contracts": source_reports, "checks": checks, "check_count": len(checks),
                "passed": all(r["passed"] for r in checks)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"checks": len(checks), "passed": evidence["passed"], "failed": [r["check"] for r in checks if not r["passed"]]}, indent=2))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
