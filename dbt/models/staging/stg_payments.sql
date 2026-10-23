select payload->>'order_id' as order_id,(payload->>'payment_sequential')::integer as payment_sequential,
payload->>'payment_type' as payment_type,(payload->>'payment_installments')::integer as payment_installments,
(payload->>'payment_value')::numeric(18,2) as payment_value,
lineage_id,observed_cut,record_sha256 from ({{ source_at_cut('payments') }}) s
