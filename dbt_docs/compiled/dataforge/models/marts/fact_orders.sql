/*
  Grain: one row per order_item (the most granular fact in this dataset).
  payment_value is an order-level measure distributed to each item row —
  aggregate it with SUM(DISTINCT order_id, payment_value) or filter to
  item_id = 1 when calculating order-level payment totals in BI queries.
*/

with order_items as (
    select * from "dataforge"."staging"."stg_order_items"
),

orders as (
    select * from "dataforge"."staging"."stg_orders"
),

payments as (
    select
        order_id,
        sum(payment_value) as total_payment_value
    from "dataforge"."staging"."stg_order_payments"
    group by order_id
),

dim_customer as (
    select customer_key, customer_id from "dataforge"."warehouse"."dim_customer"
),

dim_product as (
    select product_key, product_id from "dataforge"."warehouse"."dim_product"
),

dim_date as (
    select date_key, full_date from "dataforge"."warehouse"."dim_date"
)

select
    -- surrogate key
    md5(oi.order_id || '-' || oi.order_item_id::text)  as order_item_key,

    -- natural / degenerate keys
    oi.order_id,
    oi.order_item_id,
    o.order_status,

    -- foreign keys to dimensions
    dc.customer_key,
    dp.product_key,
    dd.date_key,

    -- measures
    oi.price,
    oi.freight_value,
    p.total_payment_value   as payment_value

from order_items oi
inner join orders o
    on oi.order_id = o.order_id
left  join payments p
    on o.order_id = p.order_id
left  join dim_customer dc
    on o.customer_id = dc.customer_id
left  join dim_product dp
    on oi.product_id = dp.product_id
left  join dim_date dd
    on o.purchased_at::date = dd.full_date