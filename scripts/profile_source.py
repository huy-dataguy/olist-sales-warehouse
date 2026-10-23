"""Profile the publisher's Olist archive without changing source records."""

import argparse
import collections
import csv
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path
import zipfile


def profile(path: Path) -> dict:
    blob = path.read_bytes()
    selected = {
        "olist_customers_dataset.csv": ("customer_id",),
        "olist_orders_dataset.csv": ("order_id",),
        "olist_order_items_dataset.csv": ("order_id", "order_item_id"),
        "olist_order_payments_dataset.csv": ("order_id", "payment_sequential"),
        "olist_products_dataset.csv": ("product_id",),
        "olist_sellers_dataset.csv": ("seller_id",),
        "product_category_name_translation.csv": ("product_category_name",),
    }
    data, inventory = {}, []
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        for member in archive.infolist():
            if not member.filename.endswith(".csv"):
                continue
            rows, count = [], 0
            with archive.open(member) as handle:
                reader = csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig"))
                for row in reader:
                    count += 1
                    if member.filename in selected:
                        rows.append(row)
            entry = {
                "file": member.filename, "rows": count,
                "uncompressed_bytes": member.file_size,
                "columns": reader.fieldnames, "in_v1": member.filename in selected,
            }
            if member.filename in selected:
                keys = [tuple(row[c] for c in selected[member.filename]) for row in rows]
                entry["natural_key"] = selected[member.filename]
                entry["duplicate_key_rows"] = len(keys) - len(set(keys))
                entry["blank_cells"] = {
                    col: n for col in reader.fieldnames
                    if (n := sum(not row[col] for row in rows))
                }
                data[member.filename] = rows
            inventory.append(entry)
    orders = {r["order_id"]: r for r in data["olist_orders_dataset.csv"]}
    customers = {r["customer_id"]: r for r in data["olist_customers_dataset.csv"]}
    products = {r["product_id"]: r for r in data["olist_products_dataset.csv"]}
    sellers = {r["seller_id"]: r for r in data["olist_sellers_dataset.csv"]}
    items = data["olist_order_items_dataset.csv"]
    payments = data["olist_order_payments_dataset.csv"]
    item_orders = {r["order_id"] for r in items}
    payment_orders = {r["order_id"] for r in payments}
    delivered_ids = {key for key, row in orders.items() if row["order_status"] == "delivered"}
    delivered_items = [r for r in items if r["order_id"] in delivered_ids]
    delivered_customers = {
        customers[orders[key]["customer_id"]]["customer_unique_id"] for key in delivered_ids
    }
    customer_orders = collections.Counter(
        customers[orders[key]["customer_id"]]["customer_unique_id"] for key in delivered_ids
    )
    item_values, freight_values, payment_values = (
        collections.defaultdict(Decimal) for _ in range(3)
    )
    for row in items:
        item_values[row["order_id"]] += Decimal(row["price"])
        freight_values[row["order_id"]] += Decimal(row["freight_value"])
    for row in payments:
        payment_values[row["order_id"]] += Decimal(row["payment_value"])
    matched = item_orders & payment_orders
    differences = {
        key: payment_values[key] - item_values[key] - freight_values[key]
        for key in matched
    }
    return {
        "artifact": str(path), "zip_bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "inventory": inventory,
        "baseline": {
            "order_status_counts": dict(sorted(collections.Counter(r["order_status"] for r in orders.values()).items())),
            "purchase_timestamp_min": min(r["order_purchase_timestamp"] for r in orders.values()),
            "purchase_timestamp_max": max(r["order_purchase_timestamp"] for r in orders.values()),
            "distinct_customers": len({r["customer_unique_id"] for r in customers.values()}),
            "delivered_orders": len(delivered_ids),
            "delivered_item_rows": len(delivered_items),
            "delivered_merchandise_value_brl": str(sum((Decimal(r["price"]) for r in delivered_items), Decimal())),
            "delivered_freight_value_brl": str(sum((Decimal(r["freight_value"]) for r in delivered_items), Decimal())),
            "delivered_unique_customers": len(delivered_customers),
            "customers_with_two_or_more_delivered_orders_all_observed_history": sum(n >= 2 for n in customer_orders.values()),
        },
        "relationships": {
            "orders_missing_customer": sum(r["customer_id"] not in customers for r in orders.values()),
            "items_missing_order": sum(r["order_id"] not in orders for r in items),
            "items_missing_product": sum(r["product_id"] not in products for r in items),
            "items_missing_seller": sum(r["seller_id"] not in sellers for r in items),
            "payments_missing_order": sum(r["order_id"] not in orders for r in payments),
            "orders_without_items": len(set(orders) - item_orders),
            "orders_without_payments": len(set(orders) - payment_orders),
            "delivered_orders_without_delivered_timestamp": sum(not orders[k]["order_delivered_customer_date"] for k in delivered_ids),
            "orders_with_items_and_payments": len(matched),
            "payment_difference_above_one_cent": sum(abs(v) > Decimal("0.01") for v in differences.values()),
            "payment_difference_above_one_real": sum(abs(v) > Decimal("1.00") for v in differences.values()),
        },
        "verification_scope": "Source profiling only; no warehouse or pipeline execution.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = profile(args.archive)
    output = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output)
