{{ config(materialized='incremental', incremental_strategy='delete+insert', on_schema_change='fail', unique_key='payment_key', indexes=[{'columns':['payment_key'],'unique':true}, {'columns':['purchase_date_key']}]) }}
select 'olist:'||p.order_id||':'||p.payment_sequential as payment_key,'olist'::text as source_system,p.order_id,
    o.customer_key,o.buyer_geography_key,o.order_status_key,o.purchase_date_key,
    coalesce(method.surrogate_key,0)::bigint as payment_method_key,p.payment_sequential,o.purchase_timestamp,
    p.payment_value as recorded_payment_value,p.payment_installments,1::integer as payment_record_count,
    'BRL'::char(3) as currency_code,p.lineage_id,{{ audit_columns() }}
from {{ ref('stg_payments') }} p join {{ ref('int_order_context') }} o using(order_id)
left join ops.dimension_key_registry method on method.namespace='olist:payment_method' and method.natural_key=p.payment_type and method.version_identity='snapshot'
where p.order_id in ({{ changed_orders() }})
