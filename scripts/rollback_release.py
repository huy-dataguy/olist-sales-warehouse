"""Plan by default; explicitly apply a fenced switch to a retained release."""
import argparse
import json
from sales_dw.config import ROOT, settings
from sales_dw.rollback_release import plan, apply


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target-release", required=True)
    p.add_argument("--expected-current", required=True)
    p.add_argument("--reason", default="")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--approved-database")
    args = p.parse_args()
    if args.apply and args.approved_database != settings()["dbname"]:
        p.error("Apply requires the exact --approved-database from the reviewed plan")
    result = apply(args.target_release, args.expected_current, args.reason) if args.apply else plan(args.target_release, args.expected_current)
    result["database"] = settings()["dbname"]
    if args.apply:
        (ROOT / "var/evidence" / ("rollback-" + result["operation_run_id"] + ".json")).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
