WITH total_time_per_user_per_day AS (
    SELECT 
        v.visitor_id AS id_visitante,
        CAST(v.session_date AS DATE) AS dia_da_visita,
        SUM(v.visit_duration_seconds) AS tempo_total_visita,
        v.referrer_type AS canal_entrada,
        v.device_type AS dispositivo
    FROM 
        {{ ref('visits') }} v
    WHERE CAST(v.session_date AS DATE) <= CURRENT_DATE
    GROUP BY 
        v.visitor_id,
        CAST(v.session_date AS DATE),
        v.referrer_type,
        v.device_type
)
SELECT
    dates.dia::date,
    total_time_per_user_per_day.canal_entrada,
    total_time_per_user_per_day.dispositivo,
    COUNT(DISTINCT total_time_per_user_per_day.id_visitante) AS total_visitantes_unicos
FROM 
    (SELECT TO_DATE(year_month_day, 'YYYYMMDD') AS dia 
     FROM {{ ref('dates') }} 
     WHERE TO_DATE(year_month_day, 'YYYYMMDD') >= '2024-03-09' AND TO_DATE(year_month_day, 'YYYYMMDD') <= CURRENT_DATE) AS dates
LEFT JOIN total_time_per_user_per_day
    ON dates.dia = total_time_per_user_per_day.dia_da_visita
GROUP BY 
    dates.dia,
    total_time_per_user_per_day.canal_entrada,
    total_time_per_user_per_day.dispositivo
ORDER BY 
    dates.dia ASC,
    total_time_per_user_per_day.canal_entrada,
    total_time_per_user_per_day.dispositivo