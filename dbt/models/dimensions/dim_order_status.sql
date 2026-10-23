{{ config(materialized='table') }}
with s as (select distinct on(order_status) order_status,lineage_id from {{ ref('stg_orders') }} order by order_status,lineage_id)
select r.surrogate_key as order_status_key,'olist'::text as source_system,s.order_status as status_code,
(s.order_status='delivered') as is_delivered,(s.order_status='canceled') as is_canceled,
encode(sha256(convert_to(s.order_status,'UTF8')),'hex') as attribute_sha256,s.lineage_id,{{ audit_columns() }}
from s join ops.dimension_key_registry r on r.namespace='olist:order_status' and r.natural_key=s.order_status and r.version_identity='snapshot'
union all select key,'system',null,false,false,repeat('0',64),null::uuid,{{ audit_columns() }} from (values(0::bigint),(-1::bigint)) u(key)
