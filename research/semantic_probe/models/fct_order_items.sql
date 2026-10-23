select
    'o1:1'::text as order_item_key,
    'o1'::text as order_id,
    101::bigint as product_key,
    1001::bigint as buyer_geography_key,
    '2018-01-01'::date as order_date,
    100.00::numeric as delivered_merchandise_value
