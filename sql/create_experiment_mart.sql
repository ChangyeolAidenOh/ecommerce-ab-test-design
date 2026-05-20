-- experiment session mart
-- experiment_id + variant 기준으로 세션별 지표를 집계하는 분석 테이블

CREATE TABLE IF NOT EXISTS experiment_session_mart (
    session_id       VARCHAR(64) PRIMARY KEY,
    user_id          VARCHAR(64) NOT NULL,
    experiment_id    VARCHAR(32) NOT NULL,
    variant          VARCHAR(16) NOT NULL,   -- 'control', 'treatment_a', 'treatment_b'
    session_start_at TIMESTAMP NOT NULL,
    session_end_at   TIMESTAMP,

    -- primary metric
    purchase_count   INT DEFAULT 0,

    -- secondary metrics
    product_clicks   INT DEFAULT 0,
    review_views     INT DEFAULT 0,
    body_type_review_views INT DEFAULT 0,
    cart_additions   INT DEFAULT 0,
    time_on_page_sec FLOAT,

    -- guardrail metrics
    bounce_flag      SMALLINT DEFAULT 0,     -- 1 if no product click in session
    scroll_depth     INT DEFAULT 0,          -- number of product cards scrolled
    sort_reverted    SMALLINT DEFAULT 0,     -- 1 if user manually reverted sort order

    -- user attributes (denormalized for fast filtering)
    height_bucket    VARCHAR(16),
    weight_bucket    VARCHAR(16),
    age_group        VARCHAR(16),

    -- metadata
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_exp_variant ON experiment_session_mart(experiment_id, variant);
CREATE INDEX idx_exp_user ON experiment_session_mart(experiment_id, user_id);
