{{ config(indexes=[{'columns':['order_id'],'unique':true}]) }}
select o.*,
    coalesce(cust.surrogate_key,0)::bigint as customer_key,
    coalesce(geo.surrogate_key,0)::bigint as buyer_geography_key,
    coalesce(status.surrogate_key,0)::bigint as order_status_key,
    coalesce(to_char(o.purchase_timestamp,'YYYYMMDD')::integer,0) as purchase_date_key,
    coalesce(to_char(o.approved_timestamp,'YYYYMMDD')::integer,0) as approved_date_key,
    coalesce(to_char(o.carrier_timestamp,'YYYYMMDD')::integer,0) as carrier_date_key,
    coalesce(to_char(o.delivered_timestamp,'YYYYMMDD')::integer,0) as delivered_date_key,
    coalesce(to_char(o.estimated_delivery_timestamp,'YYYYMMDD')::integer,0) as estimated_delivery_date_key
from {{ ref('stg_orders') }} o
left join {{ ref('stg_customers') }} c using(customer_id)
left join ops.dimension_key_registry cust on cust.namespace='olist:customer' and cust.natural_key=c.customer_unique_id and cust.version_identity='snapshot'
left join ops.dimension_key_registry geo on geo.namespace='olist:buyer_geography' and geo.natural_key=jsonb_build_array(c.postal_prefix,c.city,c.state)::text and geo.version_identity='snapshot'
left join ops.dimension_key_registry status on status.namespace='olist:order_status' and status.natural_key=o.order_status and status.version_identity='snapshot'
