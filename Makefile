.PHONY: verify-design verify-spec verify-contracts verify-semantic-offline verify-source
.NOTPARALLEL:
COMPOSE = docker compose --env-file .env -f infra/compose.yaml
WORKER = $(COMPOSE) run --rm worker
PYWORKER = $(COMPOSE) run --rm --entrypoint python worker
SOURCE_ARCHIVE ?= data/raw/olist/brazilian-ecommerce-v2.zip

.PHONY: prepare build up start stop source load-source run resume-run migrate-plan migrate verify-boot verify-runtime verify-bi refresh-bi verify-browser verify-raw verify-warehouse verify-semantic verify-security verify-performance verify-release-isolation backup verify-restore test demo

prepare:
	python scripts/prepare_local.py

source:
	python scripts/fetch_source.py

build: prepare
	$(COMPOSE) build worker airflow-init minio superset

migrate-plan:
	$(COMPOSE) run --rm migrate --superset

migrate:
	$(COMPOSE) run --rm migrate --apply --approved-project salesdw --superset

up: build
	$(COMPOSE) up -d --wait postgres minio
	$(MAKE) migrate-plan migrate
	$(COMPOSE) run --rm airflow-init
	$(COMPOSE) run --rm superset-init
	$(COMPOSE) up -d superset airflow-api airflow-scheduler airflow-dag-processor

start:
	$(COMPOSE) up -d postgres minio superset airflow-api airflow-scheduler airflow-dag-processor

stop:
	$(COMPOSE) stop

verify-boot:
	$(WORKER) doctor
	python scripts/operations.py health

load-source run: source
	$(WORKER) run

resume-run:
	test -n "$(RUN_ID)"
	$(WORKER) run --resume-from "$(RUN_ID)"

verify-runtime:
	$(PYWORKER) /workspace/scripts/verify_runtime.py all

verify-raw:
	$(PYWORKER) /workspace/scripts/verify_runtime.py raw

verify-warehouse:
	$(PYWORKER) /workspace/scripts/verify_runtime.py warehouse

verify-semantic:
	$(PYWORKER) /workspace/scripts/verify_runtime.py semantic

verify-security:
	$(PYWORKER) /workspace/scripts/verify_runtime.py security

verify-performance:
	$(PYWORKER) /workspace/scripts/verify_runtime.py performance

verify-release-isolation:
	$(PYWORKER) /workspace/scripts/verify_runtime.py isolation

verify-bi:
	$(PYWORKER) /workspace/scripts/prepare_superset_context.py
	$(MAKE) refresh-bi

# UI-only change: retain existing published release, prove idempotent metadata.
refresh-bi:
	$(COMPOSE) exec -T superset python /workspace/bi/bootstrap_superset.py
	$(COMPOSE) exec -T superset python /workspace/bi/bootstrap_superset.py
	$(PYWORKER) /workspace/scripts/verify_superset.py

verify-browser:
	uv run --no-project --with playwright python scripts/verify_superset_browser.py

analyze:
	$(PYWORKER) /workspace/scripts/analyze_business.py
	python scripts/package_analytics.py --analysis-only

backup:
	python scripts/backup_restore.py backup

verify-restore:
	python scripts/backup_restore.py drill

verify-orchestration:
	python scripts/verify_airflow.py

# Explicit isolated targets only; these scripts never reset a target.
verify-recovery:
	test -n "$(RESTORE_DB)"
	$(COMPOSE) run --rm -e SALES_DW_DATABASE="$(RESTORE_DB)" --entrypoint python worker /workspace/scripts/verify_pipeline_recovery.py

verify-faults:
	test -n "$(RESTORE_DB)"
	$(COMPOSE) run --rm -e SALES_DW_DATABASE="$(RESTORE_DB)" --entrypoint python worker /workspace/scripts/verify_faults.py

verify-correction:
	test -n "$(RESTORE_DB)"
	$(COMPOSE) run --rm -e SALES_DW_DATABASE="$(RESTORE_DB)" --entrypoint python worker /workspace/scripts/verify_correction.py

verify-publish-ack:
	test -n "$(RESTORE_DB)"
	$(COMPOSE) run --rm -e SALES_DW_DATABASE="$(RESTORE_DB)" --entrypoint python worker /workspace/scripts/verify_publish_ack.py

verify-replay:
	test -n "$(RESTORE_DB)"
	$(COMPOSE) run --rm -e SALES_DW_DATABASE="$(RESTORE_DB)" --entrypoint python worker /workspace/scripts/verify_incremental.py

package-evidence:
	python scripts/package_analytics.py

capacity retention-plan:
	python scripts/operations.py capacity

docs: prepare
	$(PYWORKER) /workspace/scripts/generate_docs.py
	$(COMPOSE) --profile docs up -d dbt-docs

test:
	PYTHONPATH=src uv run --frozen --group runtime --group test pytest -q

demo: up source run verify-bi analyze verify-boot verify-runtime

verify-design: verify-spec verify-contracts verify-semantic-offline

verify-spec:
	uv run --frozen --group design python scripts/validate_design.py

verify-contracts:
	@if [ -f "$(SOURCE_ARCHIVE)" ]; then \
		uv run --frozen --group design python scripts/verify_design_contracts.py --source "$(SOURCE_ARCHIVE)"; \
	else \
		echo "Source archive absent: validating committed contracts, fixtures and DDL only."; \
		echo "Run 'make source' (Kaggle credentials required) to also validate every source row."; \
		uv run --frozen --group design python scripts/verify_design_contracts.py; \
	fi

verify-semantic-offline:
	uv run --frozen --group design --group semantic python scripts/probe_semantics.py

verify-source:
	uv run --frozen --group design python scripts/profile_source.py data/raw/olist/brazilian-ecommerce-v2.zip --output docs/evidence/source-profile.json

