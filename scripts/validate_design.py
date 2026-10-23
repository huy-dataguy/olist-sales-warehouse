"""Validate the local design package; this is not DSH admission or runtime proof."""

import hashlib
import json
from pathlib import Path
import re
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "specs/spec-package"


def main() -> int:
    issues = []
    required = [
        "TEMPLATE_VERSION", "00-index.md", "00-contract.md", "01-product/requirements.md",
        "02-architecture/system-architecture.md", "02-architecture/consumer-workload-map.md",
        "02-architecture/adr/README.md", "03-data/data-contracts.md", "03-data/source-of-record.md",
        "03-data/data-model.md", "03-data/semantic-and-metrics.md", "04-workflow/task-graph.yaml",
        "06-verification/verification-matrix.md", "06-verification/traceability.md",
        "07-implementation/implementation-plan.md", "07-implementation/runtime-constraints.md",
        "07-implementation/dossier-admission.md", "08-operations/README.md",
        "03-data/kimball-design.md", "02-architecture/production-local.md",
        "02-architecture/security-and-governance.md", "08-operations/operating-model.md",
        "06-verification/test-strategy.md",
    ]
    for name in required:
        if not (SPEC / name).is_file():
            issues.append(f"Missing required package file: {name}")
    if issues:
        print(json.dumps({"passed": False, "issues": issues}))
        return 1
    text = (SPEC / "01-product/requirements.md").read_text()
    sections = list(re.finditer(r"^### (REQ-\d+)\s+[-—]\s+(.+)$", text, re.MULTILINE))
    req_ids = [match[1] for match in sections]
    requirement_dependencies = {}
    if not req_ids or len(req_ids) != len(set(req_ids)):
        issues.append("Requirements missing or identifiers duplicated")
    for heading in ("## Non-goals", "## Decisions", "## Open issues", "## Risk: medium"):
        if heading not in text:
            issues.append(f"Missing requirements section {heading}")
    matrix = (SPEC / "06-verification/verification-matrix.md").read_text()
    checks = dict(re.findall(r"^\| (V-\d+) \| (REQ-\d+) \|", matrix, re.MULTILINE))
    for index, match in enumerate(sections):
        body = text[match.end(): sections[index + 1].start() if index + 1 < len(sections) else text.index("\n## Decisions")]
        if "Acceptance criteria:" not in body:
            issues.append(f"No acceptance criteria for {match[1]}")
        for criterion in re.findall(r"^- (.+)$", body, re.MULTILINE):
            refs = re.findall(r"\bV-\d+\b", criterion)
            if not refs:
                issues.append(f"Criterion without verification in {match[1]}")
            for ref in refs:
                if ref not in checks:
                    issues.append(f"Unknown check {ref} in {match[1]}")
        dependency_line = re.search(r"^Depends: (.+)$", body, re.MULTILINE)
        requirement_dependencies[match[1]] = set(re.findall(r"REQ-\d+", dependency_line[1])) if dependency_line else set()
    graph = yaml.safe_load((SPEC / "04-workflow/task-graph.yaml").read_text())
    tasks = graph["tasks"]
    task_ids = [task["id"] for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        issues.append("Duplicate task identifier")
    by_id = {task["id"]: task for task in tasks}
    covered = set()
    for task in tasks:
        req = task.get("requirement_id")
        covered.add(req)
        if req not in req_ids:
            issues.append(f"Unknown requirement {req} in {task['id']}")
        if not task.get("artifacts") or not task.get("verification"):
            issues.append(f"No artifacts/checks in {task['id']}")
        for check in task.get("verification", []):
            if checks.get(check) != req:
                issues.append(f"Check/requirement mismatch {task['id']} / {check}")
        for dep in task.get("depends_on", []):
            if dep not in by_id:
                issues.append(f"Unknown dependency {dep} in {task['id']}")
    for req in set(req_ids) - covered:
        issues.append(f"Requirement without a task: {req}")
    visiting, done = set(), set()
    def visit(key):
        if key in visiting:
            issues.append(f"Task cycle at {key}")
            return
        if key in done:
            return
        visiting.add(key)
        for dep in by_id[key].get("depends_on", []):
            if dep in by_id:
                visit(dep)
        visiting.remove(key)
        done.add(key)
    for key in by_id:
        visit(key)
    def ancestors(key, trail=None):
        trail = set() if trail is None else set(trail)
        if key in trail:
            return set()
        trail.add(key)
        deps = set(by_id[key].get("depends_on", []))
        return deps | set().union(*(ancestors(dep, trail) for dep in deps if dep in by_id))
    for task in tasks:
        upstream_requirements = {by_id[key]["requirement_id"] for key in ancestors(task["id"]) if key in by_id}
        for dep in requirement_dependencies[task["requirement_id"]]:
            if dep not in req_ids or dep not in upstream_requirements:
                issues.append(f"Requirement dependency not represented in graph: {task['id']} -> {dep}")
    for path in [ROOT / "README.md", *SPEC.rglob("*.md"), *list((ROOT / "docs").glob("*.md"))]:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            if not (path.parent / target.split("#")[0]).exists():
                issues.append(f"Broken local link {path.relative_to(ROOT)} -> {target}")
    source = json.loads((ROOT / "data/source-manifest.json").read_text())
    profile = json.loads((ROOT / "docs/evidence/source-profile.json").read_text())
    if source["sha256"] != profile["sha256"]:
        issues.append("Source manifest/profile checksum mismatch")
    archive = ROOT / source["local_artifact"]
    if archive.exists() and hashlib.sha256(archive.read_bytes()).hexdigest() != source["sha256"]:
        issues.append("Local source archive checksum mismatch")
    scenarios = json.loads((ROOT / "contracts/operational-scenarios.json").read_text())["scenarios"]
    if len({row["id"] for row in scenarios}) != len(scenarios):
        issues.append("Duplicate operational scenario ID")
    for scenario in scenarios:
        if scenario["verification"] not in checks:
            issues.append(f"Unknown scenario check {scenario['verification']}")
    state_machines = json.loads((ROOT / "contracts/state-machines.json").read_text())
    for name in ("batch", "release", "pipeline_run"):
        machine = state_machines[name]
        states = set(machine["states"])
        for start, end in machine["transitions"]:
            if start not in states or end not in states or start in machine.get("terminal", []):
                issues.append(f"Invalid transition {name}: {start} -> {end}")
    for check in state_machines["publication"]["required_checks"]:
        if check not in checks:
            issues.append(f"Unknown publication check {check}")
    evidence = {
        "scope": "Design structure, local links, requirement/check/task references, DAG acyclicity and source artifact identity. Not native DSH admission or system completion.",
        "template_version": (SPEC / "TEMPLATE_VERSION").read_text().strip(),
        "requirements": len(req_ids), "tasks": len(tasks), "verification_entries": len(checks),
        "operational_scenarios": len(scenarios),
        "passed": not issues, "issues": issues,
    }
    (ROOT / "docs/evidence/design-validation.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
