-- segment analysis: body type bucket별 실험 효과 이질성 확인
-- Case 2에서 "어떤 체형 버켓에서 정렬 변경 효과가 가장 큰가" 확인

SELECT
    experiment_id,
    variant,
    height_bucket,
    weight_bucket,
    COUNT(DISTINCT user_id)                              AS users,
    COUNT(DISTINCT session_id)                           AS sessions,
    ROUND(
        AVG(CASE WHEN purchase_count > 0 THEN 1.0 ELSE 0.0 END), 5
    )                                                    AS session_cvr,
    ROUND(AVG(body_type_review_views), 1)                AS avg_bt_review_views
FROM experiment_session_mart
WHERE experiment_id = 'review_sort_v1'
  AND height_bucket IS NOT NULL
  AND weight_bucket IS NOT NULL
GROUP BY experiment_id, variant, height_bucket, weight_bucket
HAVING COUNT(DISTINCT session_id) >= 30  -- 최소 표본 필터
ORDER BY variant, height_bucket, weight_bucket;


-- 체형 필터 활성화 유저 비율 (eligible DAU 추정용)
SELECT
    DATE(session_start_at) AS dt,
    COUNT(DISTINCT user_id) AS total_users,
    COUNT(DISTINCT CASE
        WHEN height_bucket IS NOT NULL
         AND weight_bucket IS NOT NULL
        THEN user_id
    END) AS body_type_users,
    ROUND(
        COUNT(DISTINCT CASE
            WHEN height_bucket IS NOT NULL
             AND weight_bucket IS NOT NULL
            THEN user_id
        END)::NUMERIC / NULLIF(COUNT(DISTINCT user_id), 0), 3
    ) AS activation_rate
FROM experiment_session_mart
GROUP BY DATE(session_start_at)
ORDER BY dt;
