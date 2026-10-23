{{ config(materialized='table') }}
select r.surrogate_key as product_key,'olist'::text as source_system,p.product_id,'snapshot'::text as version_identity,
p.category_source,t.category_english,coalesce(t.category_english,p.category_source,'Unknown') as category,
(p.category_source is null) as category_missing,null::timestamp as valid_from,null::timestamp as valid_to,
true as is_current,false as business_effectivity_known,false as is_inferred,
encode(sha256(convert_to(p.record_sha256||coalesce(t.record_sha256,''),'UTF8')),'hex') as attribute_sha256,p.lineage_id,{{ audit_columns() }}
from {{ ref('stg_products') }} p
left join {{ ref('stg_category_translation') }} t using(category_source)
join ops.dimension_key_registry r on r.namespace='olist:product' and r.natural_key=p.product_id and r.version_identity='snapshot'
union all
select r.surrogate_key,'olist',i.product_id,'snapshot',null,null,'Unknown',true,null,null,true,false,true,
encode(sha256(convert_to('inferred:'||i.product_id,'UTF8')),'hex'),i.lineage_id,{{ audit_columns() }}
from (
  select distinct on (product_id) product_id,lineage_id
  from {{ ref('stg_order_items') }} i
  where not exists (select 1 from {{ ref('stg_products') }} p where p.product_id=i.product_id)
  order by product_id,lineage_id
) i
join ops.dimension_key_registry r on r.namespace='olist:product' and r.natural_key=i.product_id and r.version_identity='snapshot'
union all select key,'system',null,'reserved',null,null,'Unknown',true,null,null,true,false,false,repeat('0',64),null::uuid,{{ audit_columns() }}
from (values(0::bigint),(-1::bigint)) u(key)
