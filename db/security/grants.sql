-- Applied only by the controlled migration entrypoint after dedicated roles exist.
REVOKE ALL ON DATABASE sales_dw FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ops FROM PUBLIC;
GRANT CONNECT ON DATABASE sales_dw TO salesdw_ingest,salesdw_transform,salesdw_snapshot,salesdw_semantic,salesdw_publish,salesdw_analyst,salesdw_bi,salesdw_backup;
GRANT TEMPORARY ON DATABASE sales_dw TO salesdw_transform;
GRANT USAGE ON SCHEMA ops TO salesdw_ingest,salesdw_transform,salesdw_snapshot,salesdw_semantic,salesdw_publish,salesdw_backup;
GRANT USAGE ON SCHEMA landing TO salesdw_ingest,salesdw_transform,salesdw_snapshot;
GRANT SELECT ON ALL TABLES IN SCHEMA ops TO salesdw_ingest,salesdw_transform,salesdw_snapshot,salesdw_semantic,salesdw_publish,salesdw_backup;
GRANT SELECT,INSERT,UPDATE ON ops.pipeline_runs,ops.artifacts,ops.batches,ops.receipts TO salesdw_ingest;
GRANT INSERT ON ops.source_commits,ops.dq_issues,ops.state_events TO salesdw_ingest;
GRANT SELECT,INSERT ON landing.source_versions TO salesdw_ingest;
GRANT SELECT ON landing.source_versions TO salesdw_transform,salesdw_snapshot;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA ops TO salesdw_ingest,salesdw_transform,salesdw_snapshot,salesdw_publish;
GRANT USAGE,CREATE ON SCHEMA work TO salesdw_transform;
GRANT INSERT ON ops.dimension_key_registry TO salesdw_transform;
GRANT INSERT,UPDATE ON ops.pipeline_leases TO salesdw_transform;
GRANT EXECUTE ON FUNCTION ops.assert_lease(uuid,bigint),ops.checkpoint(text,bigint,uuid,bigint) TO salesdw_transform,salesdw_snapshot,salesdw_semantic,salesdw_publish;
ALTER DEFAULT PRIVILEGES FOR ROLE salesdw_transform IN SCHEMA work GRANT SELECT ON TABLES TO salesdw_snapshot;
GRANT USAGE ON SCHEMA work,warehouse_store TO salesdw_snapshot;
GRANT SELECT,INSERT ON ALL TABLES IN SCHEMA warehouse_store TO salesdw_snapshot;
GRANT MAINTAIN ON ALL TABLES IN SCHEMA warehouse_store TO salesdw_snapshot;
GRANT INSERT,UPDATE ON ops.releases,ops.check_results,ops.snapshot_relations TO salesdw_snapshot;
GRANT INSERT ON ops.lineage_edges,ops.dq_issues,ops.state_events TO salesdw_snapshot;
GRANT USAGE ON SCHEMA semantic_input,reporting TO salesdw_semantic;
GRANT SELECT ON ALL TABLES IN SCHEMA semantic_input TO salesdw_semantic;
GRANT EXECUTE ON FUNCTION ops.bound_release_id() TO salesdw_semantic;
GRANT SELECT,INSERT ON reporting.sales_monthly,reporting.sales_daily,reporting.product_monthly,reporting.seller_monthly,reporting.buyer_state_monthly TO salesdw_semantic;
GRANT INSERT ON ops.export_queries TO salesdw_semantic;
GRANT INSERT,UPDATE ON ops.published_release TO salesdw_publish;
GRANT UPDATE ON ops.releases TO salesdw_publish;
GRANT INSERT ON ops.state_events TO salesdw_publish;
GRANT USAGE ON SCHEMA warehouse TO salesdw_analyst;
GRANT SELECT ON ALL TABLES IN SCHEMA warehouse TO salesdw_analyst;
GRANT USAGE ON SCHEMA reporting TO salesdw_bi;
GRANT SELECT ON reporting.validated_sales_monthly,reporting.validated_sales_daily,
 reporting.validated_product_monthly,reporting.validated_seller_monthly,reporting.validated_buyer_state_monthly,
 reporting.pipeline_health,reporting.quality_health,reporting.release_metadata TO salesdw_bi;
GRANT USAGE ON SCHEMA landing,warehouse_store,reporting,warehouse,work TO salesdw_backup;
GRANT SELECT ON ALL TABLES IN SCHEMA landing,warehouse_store,reporting,warehouse,work TO salesdw_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE salesdw_transform IN SCHEMA work GRANT SELECT ON TABLES TO salesdw_backup;
GRANT SELECT ON public.schema_migrations TO salesdw_backup;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA ops TO salesdw_backup;
GRANT SELECT ON reporting.analytic_orders,reporting.analytic_payments,
 reporting.analytic_customers,reporting.analytic_cohorts TO salesdw_bi;
