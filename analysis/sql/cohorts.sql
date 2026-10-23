SELECT cohort_month,month_offset,cohort_size,active_customers,observed_retention
FROM reporting.analytic_cohorts WHERE release_id=%(release_id)s ORDER BY cohort_month,month_offset;
