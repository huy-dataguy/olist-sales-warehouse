select 'orders' as fact, order_id as natural_key from {{ ref('fct_orders') }} group by source_system,order_id having count(*)<>1
union all
select 'items',order_id||':'||order_item_id from {{ ref('fct_order_items') }} group by source_system,order_id,order_item_id having count(*)<>1
union all
select 'payments',order_id||':'||payment_sequential from {{ ref('fct_payments') }} group by source_system,order_id,payment_sequential having count(*)<>1
