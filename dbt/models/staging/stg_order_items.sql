select payload->>'order_id' as order_id,(payload->>'order_item_id')::integer as order_item_id,
payload->>'product_id' as product_id,payload->>'seller_id' as seller_id,
(payload->>'price')::numeric(18,2) as price,(payload->>'freight_value')::numeric(18,2) as freight_value,
lineage_id,observed_cut,record_sha256 from ({{ source_at_cut('order_items') }}) s
