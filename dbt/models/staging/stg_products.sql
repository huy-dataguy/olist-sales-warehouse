select payload->>'product_id' as product_id,nullif(payload->>'product_category_name','') as category_source,
payload as source_metadata,lineage_id,observed_cut,record_sha256 from ({{ source_at_cut('products') }}) s
