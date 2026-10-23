-- This relation is provisioned by reviewed migrations. Parse only, never dbt-build this project.
select o.*,o.purchase_timestamp::date as order_date,case when delivered_order_count=1 and customer_key>0 then customer_key end as delivered_customer_key from semantic_input.fct_orders o
