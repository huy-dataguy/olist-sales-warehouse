SELECT buyer_state,count(*) AS orders,sum(known_delivery_date_count) AS eligible_deliveries,
       sum(on_time_delivery_count) AS on_time_deliveries,
       sum(on_time_delivery_count)::numeric/nullif(sum(known_delivery_date_count),0) AS on_time_rate,
       percentile_cont(0.5) WITHIN GROUP(ORDER BY delivery_days) FILTER(WHERE known_delivery_date_count=1) AS median_delivery_days,
       avg(delivery_days) FILTER(WHERE known_delivery_date_count=1) AS average_delivery_days,
       sum(canceled_order_count) AS canceled_orders
FROM reporting.analytic_orders WHERE release_id=%(release_id)s AND month=%(month)s
GROUP BY buyer_state ORDER BY eligible_deliveries DESC,buyer_state;
