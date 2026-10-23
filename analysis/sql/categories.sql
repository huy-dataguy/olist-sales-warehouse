SELECT category,delivered_merchandise_value,delivered_item_rows,
       delivered_merchandise_value/nullif(sum(delivered_merchandise_value) OVER(),0) AS value_share,
       sum(delivered_merchandise_value) OVER(ORDER BY delivered_merchandise_value DESC,category ROWS UNBOUNDED PRECEDING)/nullif(sum(delivered_merchandise_value) OVER(),0) AS cumulative_value_share
FROM reporting.validated_product_monthly WHERE release_id=%(release_id)s AND month=%(month)s
ORDER BY delivered_merchandise_value DESC,category;
