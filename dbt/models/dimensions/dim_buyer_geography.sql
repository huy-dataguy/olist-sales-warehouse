{{ config(materialized='table') }}
with c as (
select distinct on(postal_prefix,city,state) postal_prefix,city,state,lineage_id
from {{ ref('stg_customers') }} order by postal_prefix,city,state,lineage_id)
select r.surrogate_key as buyer_geography_key,'olist'::text as source_system,c.postal_prefix,c.city,c.state,
encode(sha256(convert_to(r.natural_key,'UTF8')),'hex') as attribute_sha256,c.lineage_id,{{ audit_columns() }}
from c join ops.dimension_key_registry r on r.namespace='olist:buyer_geography'
and r.natural_key=jsonb_build_array(c.postal_prefix,c.city,c.state)::text and r.version_identity='snapshot'
union all select key,'system',null,null,null,repeat('0',64),null::uuid,{{ audit_columns() }} from (values(0::bigint),(-1::bigint)) u(key)
