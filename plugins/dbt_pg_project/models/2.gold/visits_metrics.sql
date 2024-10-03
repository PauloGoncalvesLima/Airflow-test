SELECT 
    d.day,
    COUNT(DISTINCT u.user_id) AS new_users_count,
    COUNT(DISTINCT v.visitor_id) AS visitante_unico
FROM 
    dev_silver.dates d
LEFT JOIN 
    silver.users u 
    ON d.day = CAST(u.created_at AS date)
LEFT JOIN 
    silver.visits v 
    ON d.day = CAST(v.session_date AS date)
WHERE 
    d.day BETWEEN '2023-05-01' AND CURRENT_DATE
GROUP BY 
    d.day
ORDER BY 
    d.day
