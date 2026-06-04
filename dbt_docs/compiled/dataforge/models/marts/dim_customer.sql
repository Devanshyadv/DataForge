with customers as (
    select * from "dataforge"."staging"."stg_customers"
)

select
    md5(customer_id)   as customer_key,
    customer_id,
    customer_unique_id,
    zip_code_prefix,
    city,
    state
from customers