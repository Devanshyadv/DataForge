with source as (
    select * from {{ source('raw', 'customers') }}
)

select
    customer_id,
    customer_unique_id,
    trim(customer_zip_code_prefix)    as zip_code_prefix,
    initcap(trim(customer_city))      as city,
    upper(trim(customer_state))       as state
from source
