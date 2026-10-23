select payload->>'product_category_name' as category_source,payload->>'product_category_name_english' as category_english,
lineage_id,observed_cut,record_sha256 from ({{ source_at_cut('category_translation') }}) s
