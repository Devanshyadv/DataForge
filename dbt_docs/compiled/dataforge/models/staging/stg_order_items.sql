with source as (
    select * from "dataforge"."staging"."order_items"
)

select
    order_id,
    order_item_id,
    product_id,
    seller_id,
    shipping_limit_date as ship_limit_at,
    price,
    freight_value
from source
where price >= 0
  and freight_value >= 0