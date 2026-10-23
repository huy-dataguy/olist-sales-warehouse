# AI diagram brief

Upload diagram-generation-brief.pdf and the two reference images to your chosen AI. Ask for architecture and ERD as two separate images. architecture-prompt.md, erd-prompt.md and review-prompt.md are ready to copy. For exact tables/columns, use schema-reference.json or warehouse-full-schema.mmd. The source of truth is the existing implementation, not the reference images.

The schema files contain all physical columns from the ten Warehouse tables and nineteen dimensional FK roles. References to ops/landing are outside this analytical diagram. PDF tables collapse common technical audit columns explicitly; JSON/Mermaid do not omit them. No business data, secrets or internal enterprise information are included.

Regenerate from project root: python scripts/build_ai_diagram_brief.py. Document dependencies: reportlab and pypdf; font DejaVu Sans. This exporter never connects to a database or starts services. The PDF is a generation brief, not a promise that a third-party image model will preserve dense ERD labels correctly.
