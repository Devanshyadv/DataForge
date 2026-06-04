with source as (
    select * from "dataforge"."staging"."products"
)

select
    product_id,
    coalesce(product_category_name, 'unknown') as category_name,
    -- source dataset has a typo in these two column names (lenght → length)
    product_name_lenght                        as product_name_length,
    product_description_lenght                 as product_description_length,
    product_photos_qty                         as photos_qty,
    product_weight_g                           as weight_g,
    product_length_cm                          as length_cm,
    product_height_cm                          as height_cm,
    product_width_cm                           as width_cm
from source