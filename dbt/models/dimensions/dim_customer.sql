{{ config(materialized='table') }}
with c as (select distinct on(customer_unique_id) customer_unique_id,lineage_id from {{ ref('stg_customers') }} order by customer_unique_id,lineage_id)
select r.surrogate_key as customer_key,'olist'::text as source_system,c.customer_unique_id,false as is_inferred,
encode(sha256(convert_to(c.customer_unique_id,'UTF8')),'hex') as attribute_sha256,c.lineage_id,{{ audit_columns() }}
from c join ops.dimension_key_registry r on r.namespace='olist:customer' and r.natural_key=c.customer_unique_id and r.version_identity='snapshot'
union all select key,'system',null,false,repeat('0',64),null::uuid,{{ audit_columns() }} from (values(0::bigint),(-1::bigint)) u(key)
