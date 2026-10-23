{{ config(materialized='incremental', incremental_strategy='delete+insert', on_schema_change='fail', unique_key='order_item_key', indexes=[{'columns':['order_item_key'],'unique':true}, {'columns':['purchase_date_key']}]) }}
select 'olist:'||i.order_id||':'||i.order_item_id as order_item_key,'olist'::text as source_system,i.order_id,
    o.customer_key,o.buyer_geography_key,o.order_status_key,o.purchase_date_key,
    coalesce(product.surrogate_key,0)::bigint as product_key,coalesce(seller.surrogate_key,0)::bigint as seller_key,
    i.order_item_id,o.purchase_timestamp,i.price as merchandise_value,i.freight_value,1::integer as item_row_count,
    'BRL'::char(3) as currency_code,i.lineage_id,{{ audit_columns() }}
from {{ ref('stg_order_items') }} i join {{ ref('int_order_context') }} o using(order_id)
left join ops.dimension_key_registry product on product.namespace='olist:product' and product.natural_key=i.product_id and product.version_identity='snapshot'
left join ops.dimension_key_registry seller on seller.namespace='olist:seller' and seller.natural_key=i.seller_id and seller.version_identity='snapshot'
where i.order_id in ({{ changed_orders() }})
