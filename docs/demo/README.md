# Interview demo kit

Current deliverables: [output/demo-kit](../../output/demo-kit/README.md). The original design-only graphics in `docs/visuals` remain historical; do not rename old Metabase or planned-runtime evidence as Superset implementation proof.

## Authoring and regeneration

`report-short-template.md` is the current editable report source; `report-template.md` retains the prior detailed source. `scripts/build_demo_kit.py` binds values to the verified analysis release and exports the public allowlist. Run `python scripts/build_demo_kit.py --report-only` to keep existing diagrams/schema byte-for-byte while updating the report. No services, migrations, pipeline or credentials are accessed by the exporter.

The PDF report is now 5 pages: source/scope, the user-provided architecture image, the unchanged schema, workflow/quality and business results. The image is inserted without pixel edits; its caption explains seven processed feeds out of nine archive files and Warehouse ownership of dimension/fact storage. The separate architecture PDF retains 10 vector pages. Raw sources, secrets, backups, volumes and customer-level records are not packaged. The manifest records input/output checksums and bounded evidence scope.

## Verification and lessons

- Inspect both the PNG figures and rendered PDF pages. Browser bounds checks catch label width/canvas overflow, but do not replace visual review or Warehouse runtime checks.
- Allocate page space before embedding a landscape figure. Long explanatory tables after a full-width diagram caused automatic extra pages; the handoff uses concise figure captions and moves full explanations to prose sections and speaker notes.
- Keep diagram relationships faithful to contracts. Schema export verifies all ten relations, displayed columns against migration 001, and nineteen dimension FK roles; no fact-to-fact FK is emitted. Shared routing lanes in the compact picture are a presentation device, not a new database table.
- Bind the business examples and screenshots to the same handoff release. Distinguish current health/UI checks from historical retry, replay and DWH restore evidence. Re-exporting documents does not rerun or newly certify those scenarios.

Design checks and tests remain independent: `make verify-design` and `make test`. Never use a document-export PASS as production acceptance.
