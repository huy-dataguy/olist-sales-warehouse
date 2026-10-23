{{ config(materialized='incremental', incremental_strategy='delete+insert', on_schema_change='fail', unique_key='order_key', indexes=[{'columns':['order_key'],'unique':true}, {'columns':['purchase_date_key']}]) }}
with items as (
    select order_id,sum(price) as merchandise,sum(freight_value) as freight,count(*)::integer as n
    from {{ ref('stg_order_items') }} group by order_id
), payments as (
    select order_id,sum(payment_value) as amount,count(*)::integer as n
    from {{ ref('stg_payments') }} group by order_id
)
select 'olist:'||o.order_id as order_key,'olist'::text as source_system,o.order_id,
    o.customer_key,o.buyer_geography_key,o.order_status_key,o.purchase_date_key,
    o.approved_date_key,o.carrier_date_key,o.delivered_date_key,o.estimated_delivery_date_key,
    o.customer_id as source_customer_id,o.purchase_timestamp,o.approved_timestamp,o.carrier_timestamp,
    o.delivered_timestamp,o.estimated_delivery_timestamp,
    1::integer as order_count,(o.order_status='delivered')::integer as delivered_order_count,
    (o.order_status='canceled')::integer as canceled_order_count,
    i.merchandise::numeric(18,2) as item_merchandise_total,i.freight::numeric(18,2) as item_freight_total,
    p.amount::numeric(18,2) as recorded_payment_total,
    coalesce(i.n,0)::integer as item_row_count,coalesce(p.n,0)::integer as payment_record_count,
    (i.n is not null) as has_items,(p.n is not null) as has_payments,
    (o.order_status='delivered' and o.delivered_timestamp is null) as missing_delivery_timestamp,
    (coalesce(o.approved_timestamp<o.purchase_timestamp,false)
      or coalesce(o.carrier_timestamp<o.purchase_timestamp,false)
      or coalesce(o.delivered_timestamp<o.purchase_timestamp,false)) as temporal_anomaly,
    (o.order_status='delivered' and o.delivered_timestamp is not null)::integer as known_delivery_date_count,
    (o.order_status='delivered' and o.delivered_timestamp is not null
      and o.delivered_timestamp::date<=o.estimated_delivery_timestamp::date)::integer as on_time_delivery_count,
    case when o.order_status='delivered' and o.delivered_timestamp>=o.purchase_timestamp
      then extract(epoch from o.delivered_timestamp-o.purchase_timestamp) end as purchase_to_delivery_seconds,
    'BRL'::char(3) as currency_code,o.lineage_id,{{ audit_columns() }}
from {{ ref('int_order_context') }} o
left join items i using(order_id) left join payments p using(order_id)
where o.order_id in ({{ changed_orders() }})
