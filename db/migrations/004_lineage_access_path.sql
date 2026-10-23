-- Access path for scoped lineage/reconciliation, not an atomic reporting join.
CREATE INDEX fct_orders_release_order ON warehouse_store.fct_orders(release_id,order_id);
