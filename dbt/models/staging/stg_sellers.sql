select payload->>'seller_id' as seller_id,payload->>'seller_city' as seller_city,payload->>'seller_state' as seller_state,
payload->>'seller_zip_code_prefix' as seller_zip_code_prefix,
lineage_id,observed_cut,record_sha256 from ({{ source_at_cut('sellers') }}) s
