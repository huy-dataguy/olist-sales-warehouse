-- Static views only: every actual metric query must supply a validated session binding.
CREATE VIEW semantic_input.metric_orders AS
SELECT o.*,o.purchase_timestamp::date AS order_date,
       CASE WHEN o.delivered_order_count=1 AND o.customer_key>0 THEN o.customer_key END AS delivered_customer_key
FROM semantic_input.fct_orders o;

CREATE VIEW semantic_input.metric_order_items AS
SELECT i.*,i.purchase_timestamp::date AS order_date,
       CASE WHEN s.is_delivered THEN i.merchandise_value ELSE 0::numeric END AS delivered_merchandise_value,
       CASE WHEN s.is_delivered THEN i.item_row_count ELSE 0 END AS delivered_item_rows
FROM semantic_input.fct_order_items i
JOIN semantic_input.dim_order_status s USING(release_id,order_status_key);

CREATE VIEW semantic_input.time_spine AS
SELECT day::date AS date_day FROM generate_series('2016-01-01'::timestamp,'2030-12-31'::timestamp,interval '1 day') day;
