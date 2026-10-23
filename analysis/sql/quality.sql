SELECT rule_id,severity,affected_records FROM reporting.quality_health
WHERE pipeline_run_id=%(pipeline_run_id)s ORDER BY rule_id;
