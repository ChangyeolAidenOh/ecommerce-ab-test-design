-- guardrail metrics: bounce rate + scroll depth by variant
-- NIT 판정에 사용할 가드레일 지표 집계

SELECT
    experiment_id,
    variant,
    COUNT(DISTINCT session_id)       AS sessions,
    ROUND(AVG(bounce_flag), 5)       AS bounce_rate,
    ROUND(AVG(scroll_depth), 1)      AS avg_scroll_depth,
    ROUND(AVG(sort_reverted), 5)     AS sort_revert_rate
FROM experiment_session_mart
WHERE experiment_id = 'review_sort_v1'
GROUP BY experiment_id, variant
ORDER BY variant;


-- guardrail 추이 (n 증가에 따른 안정화 확인)
-- UNCONFIRMED → SAFE 전환 시점 파악용
SELECT
    experiment_id,
    variant,
    decile,
    COUNT(DISTINCT session_id) AS sessions,
    ROUND(AVG(bounce_flag), 5) AS bounce_rate,
    ROUND(AVG(scroll_depth), 1) AS avg_scroll_depth
FROM (
    SELECT
        experiment_id,
        variant,
        session_id,
        bounce_flag,
        scroll_depth,
        NTILE(10) OVER (
            PARTITION BY experiment_id, variant
            ORDER BY session_start_at
        ) AS decile
    FROM experiment_session_mart
    WHERE experiment_id = 'gif_feed_density_v1'
) sub
GROUP BY experiment_id, variant, decile
ORDER BY variant, decile;
