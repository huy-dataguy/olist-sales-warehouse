SELECT m.*,p.delivered_merchandise_value AS previous_month_value,
       (m.delivered_merchandise_value-p.delivered_merchandise_value)/nullif(p.delivered_merchandise_value,0) AS value_mom,
       y.delivered_merchandise_value AS previous_year_value,
       (m.delivered_merchandise_value-y.delivered_merchandise_value)/nullif(y.delivered_merchandise_value,0) AS value_yoy
FROM reporting.validated_sales_monthly m
LEFT JOIN reporting.validated_sales_monthly p ON p.release_id=m.release_id AND p.month=m.month-interval '1 month'
LEFT JOIN reporting.validated_sales_monthly y ON y.release_id=m.release_id AND y.month=m.month-interval '1 year'
WHERE m.release_id=%(release_id)s ORDER BY m.month;
