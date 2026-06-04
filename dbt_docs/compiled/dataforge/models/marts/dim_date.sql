with purchase_dates as (
    select distinct purchased_at::date as full_date
    from "dataforge"."staging"."stg_orders"
    where purchased_at is not null
)

select
    to_char(full_date, 'YYYYMMDD')::integer          as date_key,
    full_date,
    extract(year    from full_date)::integer          as year,
    extract(quarter from full_date)::integer          as quarter,
    extract(month   from full_date)::integer          as month,
    trim(to_char(full_date, 'Month'))                 as month_name,
    extract(day     from full_date)::integer          as day,
    extract(dow     from full_date)::integer          as day_of_week,
    trim(to_char(full_date, 'Day'))                   as day_name,
    extract(dow from full_date) in (0, 6)             as is_weekend
from purchase_dates