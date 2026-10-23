select payload->>'order_id' as order_id,payload->>'customer_id' as customer_id,payload->>'order_status' as order_status,
(payload->>'order_purchase_timestamp')::timestamp as purchase_timestamp,
nullif(payload->>'order_approved_at','')::timestamp as approved_timestamp,
nullif(payload->>'order_delivered_carrier_date','')::timestamp as carrier_timestamp,
nullif(payload->>'order_delivered_customer_date','')::timestamp as delivered_timestamp,
(payload->>'order_estimated_delivery_date')::timestamp as estimated_delivery_timestamp,
lineage_id,observed_cut,record_sha256 from ({{ source_at_cut('orders') }}) s
