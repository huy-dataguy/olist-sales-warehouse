{% macro source_at_cut(entity) -%}
select distinct on (natural_key)
    source_version_id as lineage_id, source_cut as observed_cut, payload, record_sha256
from {{ source('landing','source_versions') }}
where entity = '{{ entity }}' and source_cut <= {{ var('source_cut') }}
order by natural_key, source_cut desc
{%- endmacro %}

{% macro audit_columns() -%}
{{ var('source_cut') }}::bigint as source_cut,
'{{ var('pipeline_run_id') }}'::uuid as created_run_id,
'{{ var('pipeline_run_id') }}'::uuid as last_changed_run_id
{%- endmacro %}

{% macro changed_orders() -%}
{% if is_incremental() %}
  select payload->>'order_id' as order_id from {{ source('landing','source_versions') }}
  where entity in ('orders','order_items','payments')
    and source_cut > coalesce((select source_cut from ops.model_checkpoints where model_name='{{ this.identifier }}'),0)
    and source_cut <= {{ var('source_cut') }}
  union
  select order_id from {{ ref('stg_orders') }} where exists (
    select 1 from {{ source('landing','source_versions') }}
    where entity in ('customers','products','sellers','category_translation')
      and source_cut > coalesce((select source_cut from ops.model_checkpoints where model_name='{{ this.identifier }}'),0)
      and source_cut <= {{ var('source_cut') }}
  )
{% else %}
  select order_id from {{ ref('stg_orders') }}
{% endif %}
{%- endmacro %}
