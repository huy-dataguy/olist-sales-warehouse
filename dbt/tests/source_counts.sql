select 'orders' as entity where (select count(*) from {{ ref('stg_orders') }})<>(select count(*) from {{ ref('fct_orders') }})
union all
select 'items' where (select count(*) from {{ ref('stg_order_items') }})<>(select count(*) from {{ ref('fct_order_items') }})
union all
select 'payments' where (select count(*) from {{ ref('stg_payments') }})<>(select count(*) from {{ ref('fct_payments') }})
