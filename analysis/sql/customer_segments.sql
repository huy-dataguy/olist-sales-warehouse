SELECT frequency_segment,count(*) AS customers,sum(delivered_orders) AS delivered_orders,
       sum(observed_merchandise_value) AS observed_merchandise_value,
       avg(recency_days) AS average_recency_days
FROM reporting.analytic_customers WHERE release_id=%(release_id)s
GROUP BY frequency_segment ORDER BY frequency_segment;
