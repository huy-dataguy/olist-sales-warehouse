SELECT payment_method,count(*) AS payment_records,count(DISTINCT order_id) AS orders_using_method,
       sum(recorded_payment_value) AS recorded_payment_value,
       avg(payment_installments) AS average_installments
FROM reporting.analytic_payments WHERE release_id=%(release_id)s AND month=%(month)s
GROUP BY payment_method ORDER BY recorded_payment_value DESC,payment_method;
