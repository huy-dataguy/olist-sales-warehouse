select 'items' as entity where
(select sum(price) from {{ ref('stg_order_items') }}) is distinct from (select sum(merchandise_value) from {{ ref('fct_order_items') }})
union all select 'freight' where
(select sum(freight_value) from {{ ref('stg_order_items') }}) is distinct from (select sum(freight_value) from {{ ref('fct_order_items') }})
union all select 'payments' where
(select sum(payment_value) from {{ ref('stg_payments') }}) is distinct from (select sum(recorded_payment_value) from {{ ref('fct_payments') }})
