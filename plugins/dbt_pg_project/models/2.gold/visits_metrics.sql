
WITH visit_counts AS (
    SELECT
        v.session_date AS date_day,
        COUNT(DISTINCT v.visitor_id) AS visitor_count,
        round(coalesce (AVG(CASE WHEN v.visit_duration_seconds > 0 THEN v.visit_duration_seconds END) / 60, 0),2) as visit_time_spend_in_minutes
    FROM
        {{ ref('visits') }} v
    WHERE
        v.session_date BETWEEN '2023-05-01' AND CURRENT_DATE
    GROUP BY
        v.session_date
),
user_counts AS (
    SELECT
        DATE(u.created_at) AS date_day,
        COUNT(DISTINCT u.user_id) AS user_count
    FROM
        {{ ref('users') }} u
    WHERE
        u.created_at BETWEEN '2023-05-01' AND (CURRENT_DATE + INTERVAL '1 day')
    GROUP BY
        DATE(u.created_at)
),
dates AS (
    SELECT
        d.date_day
    FROM
        {{ ref('dates') }} d
    WHERE
        d.date_day BETWEEN '2023-05-01' AND CURRENT_DATE
)
SELECT
    d.date_day,
    COALESCE(vc.visitor_count, 0) AS visitor_count,
    COALESCE(uc.user_count, 0) AS user_count,
    coalesce(vc.visit_time_spend_in_minutes, 0) as visit_time_spend_in_minutes
FROM
    dates d
    LEFT JOIN visit_counts vc ON vc.date_day = d.date_day
    LEFT JOIN user_counts uc ON uc.date_day = d.date_day
ORDER BY
    d.date_day