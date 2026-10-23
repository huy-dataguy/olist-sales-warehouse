-- Published-only analytical read models. Never join atomic facts together.
-- Existing MetricFlow outputs remain authoritative for the eight core KPIs.
CREATE VIEW reporting.analytic_orders AS
SELECT o.release_id,o.order_id,o.customer_key,o.purchase_timestamp,
       date_trunc('month',o.purchase_timestamp)::date AS month,
       g.state AS buyer_state,s.status_code AS order_status,
       o.order_count,o.delivered_order_count,o.canceled_order_count,
       CASE WHEN o.delivered_order_count=1 THEN coalesce(o.item_merchandise_total,0) ELSE 0 END AS delivered_merchandise_value,
       o.item_merchandise_total,o.item_freight_total,o.recorded_payment_total,
       o.item_row_count,o.payment_record_count,o.has_items,o.has_payments,
       o.missing_delivery_timestamp,o.temporal_anomaly,
       o.known_delivery_date_count,o.on_time_delivery_count,
       o.purchase_to_delivery_seconds/86400.0 AS delivery_days
FROM warehouse_store.fct_orders o
JOIN ops.releases r USING(release_id)
JOIN warehouse_store.dim_buyer_geography g USING(release_id,buyer_geography_key)
JOIN warehouse_store.dim_order_status s USING(release_id,order_status_key)
WHERE r.state='published';

CREATE VIEW reporting.analytic_payments AS
SELECT p.release_id,p.payment_key,p.order_id,p.customer_key,
       date_trunc('month',p.purchase_timestamp)::date AS month,
       m.payment_type AS payment_method,g.state AS buyer_state,s.status_code AS order_status,
       p.recorded_payment_value,p.payment_installments,p.payment_record_count
FROM warehouse_store.fct_payments p
JOIN ops.releases r USING(release_id)
JOIN warehouse_store.dim_payment_method m USING(release_id,payment_method_key)
JOIN warehouse_store.dim_buyer_geography g USING(release_id,buyer_geography_key)
JOIN warehouse_store.dim_order_status s USING(release_id,order_status_key)
WHERE r.state='published';

CREATE VIEW reporting.analytic_customers AS
WITH base AS (
 SELECT release_id,customer_key,min(purchase_timestamp)::date AS first_purchase,
        max(purchase_timestamp)::date AS last_purchase,count(*) AS delivered_orders,
        sum(delivered_merchandise_value) AS observed_merchandise_value
 FROM reporting.analytic_orders
 WHERE delivered_order_count=1 AND customer_key>0 AND purchase_timestamp<'2018-09-01'
 GROUP BY release_id,customer_key
)
SELECT *,date_trunc('month',first_purchase)::date AS cohort_month,
       '2018-08-31'::date AS analysis_date,'2018-08-31'::date-last_purchase AS recency_days,
       CASE WHEN delivered_orders>=3 THEN '3+ delivered orders'
            WHEN delivered_orders=2 THEN '2 delivered orders' ELSE '1 delivered order' END AS frequency_segment,
       CASE WHEN '2018-08-31'::date-last_purchase<=90 THEN '0-90 days'
            WHEN '2018-08-31'::date-last_purchase<=180 THEN '91-180 days' ELSE '181+ days' END AS recency_segment
FROM base;

CREATE VIEW reporting.analytic_cohorts AS
WITH cohorts AS (
 SELECT release_id,cohort_month,count(*) AS cohort_size
 FROM reporting.analytic_customers GROUP BY release_id,cohort_month
), activity AS (
 SELECT o.release_id,c.cohort_month,
        ((extract(year FROM o.month)-extract(year FROM c.cohort_month))*12+extract(month FROM o.month)-extract(month FROM c.cohort_month))::integer AS month_offset,
        count(DISTINCT o.customer_key) AS active_customers
 FROM reporting.analytic_orders o
 JOIN reporting.analytic_customers c USING(release_id,customer_key)
 WHERE o.delivered_order_count=1 AND o.purchase_timestamp<'2018-09-01'
 GROUP BY o.release_id,c.cohort_month,o.month
), observed AS (
 SELECT release_id,max(month) AS last_observed_month FROM reporting.analytic_orders
 WHERE delivered_order_count=1 AND purchase_timestamp<'2018-09-01' GROUP BY release_id
)
SELECT c.release_id,c.cohort_month,n.month_offset,c.cohort_size,
       coalesce(a.active_customers,0) AS active_customers,
       coalesce(a.active_customers,0)::numeric/nullif(c.cohort_size,0) AS observed_retention
FROM cohorts c JOIN observed o USING(release_id)
CROSS JOIN generate_series(0,6) n(month_offset)
LEFT JOIN activity a ON a.release_id=c.release_id AND a.cohort_month=c.cohort_month AND a.month_offset=n.month_offset
WHERE c.cohort_month+n.month_offset*interval '1 month'<=o.last_observed_month;
