# Kimball Warehouse constellation

Logical ERD. Dimension relationships are shared across processes; order_id is retained as a degenerate dimension. There are no fact-to-fact reporting relationships.

```mermaid
erDiagram
    DIM_CUSTOMER ||--o{ FCT_ORDERS : customer
    DIM_CUSTOMER ||--o{ FCT_ORDER_ITEMS : customer
    DIM_CUSTOMER ||--o{ FCT_PAYMENTS : customer
    DIM_BUYER_GEOGRAPHY ||--o{ FCT_ORDERS : order_address
    DIM_BUYER_GEOGRAPHY ||--o{ FCT_ORDER_ITEMS : order_address
    DIM_BUYER_GEOGRAPHY ||--o{ FCT_PAYMENTS : order_address
    DIM_DATE ||--o{ FCT_ORDERS : five_date_roles
    DIM_DATE ||--o{ FCT_ORDER_ITEMS : purchase_date
    DIM_DATE ||--o{ FCT_PAYMENTS : purchase_context
    DIM_ORDER_STATUS ||--o{ FCT_ORDERS : accepted_status
    DIM_ORDER_STATUS ||--o{ FCT_ORDER_ITEMS : accepted_status
    DIM_ORDER_STATUS ||--o{ FCT_PAYMENTS : accepted_status
    DIM_PRODUCT ||--o{ FCT_ORDER_ITEMS : product_version
    DIM_SELLER ||--o{ FCT_ORDER_ITEMS : seller
    DIM_PAYMENT_METHOD ||--o{ FCT_PAYMENTS : method
```

Every consumer relation is scoped by release_id; physical fact FKs reference (release_id, dimension_key). fct_orders is an accumulating snapshot of one order; item/payment facts retain their independent transaction grains.

Detailed bus matrix, change policies and measures: [Kimball design](../specs/spec-package/03-data/kimball-design.md).
