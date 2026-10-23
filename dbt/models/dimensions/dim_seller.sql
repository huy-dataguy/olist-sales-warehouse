{{ config(materialized='table') }}
select r.surrogate_key as seller_key,'olist'::text as source_system,s.seller_id,s.seller_city,s.seller_state,s.seller_zip_code_prefix,
false as is_inferred,s.record_sha256 as attribute_sha256,s.lineage_id,{{ audit_columns() }}
from {{ ref('stg_sellers') }} s join ops.dimension_key_registry r on r.namespace='olist:seller' and r.natural_key=s.seller_id and r.version_identity='snapshot'
union all select key,'system',null,null,null,null,false,repeat('0',64),null::uuid,{{ audit_columns() }} from (values(0::bigint),(-1::bigint)) u(key)
