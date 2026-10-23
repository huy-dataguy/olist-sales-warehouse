{{ config(indexes=[{'columns':['customer_id'],'unique':true}]) }}
select payload->>'customer_id' as customer_id,payload->>'customer_unique_id' as customer_unique_id,
payload->>'customer_zip_code_prefix' as postal_prefix,payload->>'customer_city' as city,payload->>'customer_state' as state,
lineage_id,observed_cut,record_sha256 from ({{ source_at_cut('customers') }}) s
