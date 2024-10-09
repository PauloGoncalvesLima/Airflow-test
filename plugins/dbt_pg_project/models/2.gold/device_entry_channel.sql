WITH total_time_per_user_per_day AS (
    SELECT 
        v.visitor_id AS visitor_id,
        CAST(v.session_date AS DATE) AS visit_day,
        SUM(v.visit_duration_seconds) AS total_visit_duration,
        v.referrer_type AS entry_channel,
        v.device_type AS device,
        ROUND(COALESCE(AVG(CASE WHEN v.visit_duration_seconds > 0 THEN v.visit_duration_seconds END) / 60, 0), 2) AS avg_visit_time_in_minutes
    FROM 
        {{ ref('visits') }} v
    WHERE CAST(v.session_date AS DATE) <= CURRENT_DATE
    GROUP BY 
        v.visitor_id,
        CAST(v.session_date AS DATE),
        v.referrer_type,
        v.device_type
),
dates AS (
    SELECT TO_DATE(year_month_day, 'YYYYMMDD') AS day 
    FROM {{ ref('dates') }} 
    WHERE TO_DATE(year_month_day, 'YYYYMMDD') >= '2024-03-09' AND TO_DATE(year_month_day, 'YYYYMMDD') <= CURRENT_DATE
),
entry_device_combinations AS (
    SELECT DISTINCT entry_channel, device
    FROM total_time_per_user_per_day
),
date_entry_device AS (
    SELECT day, entry_channel, device
    FROM dates
    CROSS JOIN entry_device_combinations
),
aggregated_data AS (
    SELECT
        visit_day,
        entry_channel,
        device,
        COUNT(DISTINCT visitor_id) AS unique_visitors,
        AVG(avg_visit_time_in_minutes) AS avg_visit_time_in_minutes
    FROM total_time_per_user_per_day
    GROUP BY visit_day, entry_channel, device
)
SELECT
    date_entry_device.day,
    date_entry_device.entry_channel,
    date_entry_device.device,
    COALESCE(aggregated_data.unique_visitors, 0) AS unique_visitors,
    COALESCE(aggregated_data.avg_visit_time_in_minutes, 0) AS avg_visit_time_in_minutes
FROM date_entry_device
LEFT JOIN aggregated_data
    ON date_entry_device.day = aggregated_data.visit_day
    AND date_entry_device.entry_channel = aggregated_data.entry_channel
    AND date_entry_device.device = aggregated_data.device
ORDER BY 
    date_entry_device.day ASC,
    date_entry_device.entry_channel,
    date_entry_device.device
