-- primary metric: session CVR by experiment variant
-- 실험군/대조군별 세션 전환율 집계

SELECT
    experiment_id,
    variant,
    COUNT(DISTINCT user_id)                              AS users,
    COUNT(DISTINCT session_id)                           AS sessions,
    SUM(CASE WHEN purchase_count > 0 THEN 1 ELSE 0 END) AS converted_sessions,
    ROUND(
        AVG(CASE WHEN purchase_count > 0 THEN 1.0 ELSE 0.0 END), 5
    )                                                    AS session_cvr
FROM experiment_session_mart
WHERE experiment_id = 'gif_feed_density_v1'
GROUP BY experiment_id, variant
ORDER BY variant;


-- daily trend (peeking 대신 주 1회 확인용)
SELECT
    experiment_id,
    variant,
    DATE(session_start_at) AS dt,
    COUNT(DISTINCT session_id) AS sessions,
    ROUND(
        AVG(CASE WHEN purchase_count > 0 THEN 1.0 ELSE 0.0 END), 5
    ) AS daily_cvr
FROM experiment_session_mart
WHERE experiment_id = 'gif_feed_density_v1'
GROUP BY experiment_id, variant, DATE(session_start_at)
ORDER BY dt, variant;
