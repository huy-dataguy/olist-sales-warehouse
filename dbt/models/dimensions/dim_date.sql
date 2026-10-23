{{ config(materialized='table') }}
select to_char(day,'YYYYMMDD')::integer as date_key,'system'::text as source_system,day::date as full_date,
date_trunc('month',day)::date as month_start,extract(day from day)::smallint as day,
extract(month from day)::smallint as month,extract(quarter from day)::smallint as quarter,
extract(year from day)::smallint as year,extract(isodow from day)::smallint as weekday,
encode(sha256(convert_to(day::date::text,'UTF8')),'hex') as attribute_sha256,null::uuid as lineage_id,{{ audit_columns() }}
from generate_series('2016-01-01'::timestamp,'2030-12-31'::timestamp,interval '1 day') day
union all select key,'system',null,null,null,null,null,null,null,repeat('0',64),null::uuid,{{ audit_columns() }} from (values(0),(-1)) u(key)
