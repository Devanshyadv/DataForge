with products as (
    select * from "dataforge"."staging"."stg_products"
)

select
    md5(product_id)   as product_key,
    product_id,
    category_name,
    photos_qty,
    weight_g,
    length_cm,
    height_cm,
    width_cm
from products