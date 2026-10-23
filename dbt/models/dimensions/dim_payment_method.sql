{{ config(materialized='table') }}
with p as (select distinct on(payment_type) payment_type,lineage_id from {{ ref('stg_payments') }} order by payment_type,lineage_id)
select r.surrogate_key as payment_method_key,'olist'::text as source_system,p.payment_type,
encode(sha256(convert_to(p.payment_type,'UTF8')),'hex') as attribute_sha256,p.lineage_id,{{ audit_columns() }}
from p join ops.dimension_key_registry r on r.namespace='olist:payment_method' and r.natural_key=p.payment_type and r.version_identity='snapshot'
union all select key,'system',null,repeat('0',64),null::uuid,{{ audit_columns() }} from (values(0::bigint),(-1::bigint)) u(key)
