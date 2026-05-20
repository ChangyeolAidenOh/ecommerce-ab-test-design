# 이벤트 로깅 및 실험 마트 설계

**작성일:** 2026-05-05

---

## 개요

실험 설계서(Case 1, Case 2)에서 정의한 지표를 실제로 측정하려면, 앱에서 어떤 이벤트를 수집하고 어떤 테이블 구조로 집계해야 하는지가 사전에 정의되어야 한다. 본 문서는 실험 지표 집계에 필요한 이벤트 로깅 요구사항과 분석용 마트 테이블 설계를 정리한다.

---

## 필요 이벤트

### Case 1: GIF 피드 밀도 실험

| 이벤트 | 트리거 시점 | 필수 속성 |
|---|---|---|
| session_start | 앱 포그라운드 진입 | session_id, user_id, timestamp |
| product_impression | 피드에서 상품 카드 노출 | session_id, product_id, position, is_gif |
| product_click | 상품 상세 진입 | session_id, product_id |
| purchase | 구매 완료 | session_id, user_id, product_id, amount |
| session_end | 앱 백그라운드 또는 5분 비활성 | session_id, timestamp, scroll_depth |

scroll_depth: session_end 시점에 유저가 스크롤한 상품 카드 수를 기록. bounce 판정은 product_click이 0인 세션으로 정의.

### Case 2: 체형 리뷰 정렬 실험

| 이벤트 | 트리거 시점 | 필수 속성 |
|---|---|---|
| category_view | 카테고리 목록 진입 | session_id, category_id, sort_type, body_type_filter_on |
| product_click | 상품 상세 진입 | session_id, product_id |
| review_section_view | 리뷰 탭 진입 | session_id, product_id |
| body_type_review_view | "내 체형만" 필터 적용 | session_id, product_id, height_bucket, weight_bucket |
| sort_change | 유저가 정렬 수동 변경 | session_id, from_sort, to_sort |
| cart_add | 장바구니 추가 | session_id, product_id |
| purchase | 구매 완료 | session_id, user_id, product_id, amount |
| return_request | 반품 신청 | user_id, order_id, product_id, days_since_purchase |

sort_change 이벤트는 guardrail(탐색 포기율) 측정에 사용. treatment 유저가 정렬을 수동으로 되돌린 비율을 추적.

---

## 실험 마트 테이블

실험 분석을 위한 세션 단위 집계 테이블. DDL은 `sql/create_experiment_mart.sql` 참조.

### 테이블: experiment_session_mart

세션 1행 = 한 유저의 한 실험 세션. experiment_id와 variant는 유저 단위로 고정(randomization unit = user).

핵심 컬럼:

| 컬럼 | 타입 | 설명 |
|---|---|---|
| session_id | VARCHAR | PK |
| user_id | VARCHAR | 유저 식별자 |
| experiment_id | VARCHAR | 실험 식별자 |
| variant | VARCHAR | control / treatment_a / treatment_b |
| purchase_count | INT | 세션 내 구매 수 (primary: >0이면 전환) |
| bounce_flag | SMALLINT | 상품 클릭 없이 이탈 = 1 (guardrail) |
| scroll_depth | INT | 스크롤한 상품 카드 수 (guardrail) |
| sort_reverted | SMALLINT | 정렬 수동 변경 = 1 (Case 2 guardrail) |
| body_type_review_views | INT | 체형 리뷰 열람 수 (Case 2 secondary) |
| height_bucket | VARCHAR | 유저 체형 버켓 (세그먼트 분석용) |
| weight_bucket | VARCHAR | 유저 체형 버켓 (세그먼트 분석용) |

---

## SQL 쿼리 구성

`sql/` 폴더에 실험 지표 집계 쿼리를 미리 설계해두었다.

| 파일 | 용도 |
|---|---|
| create_experiment_mart.sql | 마트 테이블 DDL |
| metric_session_cvr.sql | Primary metric: variant별 Session CVR + 일별 추이 |
| guardrail_bounce_scroll.sql | Guardrail: bounce rate, scroll depth, decile별 안정화 추이 |
| segment_body_type.sql | 체형 버켓별 CVR 이질성 + 체형 필터 활성화 비율 추정 |

---

## Attribution 고려사항

Case 2(체형 리뷰 정렬)에서 구매가 발생했을 때, 정렬 변경이 구매에 기여한 정도를 판단하려면 단순 라스트 터치가 아닌 funnel touchpoint 기록이 필요하다.

기록해야 할 터치포인트 경로:

```
category_view (sort_type=체형리뷰순)
  → product_click
    → review_section_view
      → body_type_review_view
        → cart_add
          → purchase
```

이 경로에서 "정렬 변경이 어느 단계에 영향을 주었는가"를 확인할 수 있다. 예를 들어 정렬 변경 후 product_click은 늘었지만 purchase는 변하지 않았다면, 정렬이 상품 발견에는 기여했지만 최종 전환에는 기여하지 않은 것이다.

현재 프로젝트에서는 Last-Touch 기준으로 Primary metric을 측정하되, 위 funnel touchpoint를 secondary 분석으로 기록하는 구조를 제안한다. Multi-Touch Attribution이나 Shapley Value 기반 기여도 배분은 데이터 축적 후 후속 분석으로 확장 가능하다.

---

*본 문서는 실험 설계서의 지표 정의를 실제 데이터 수집·집계로 연결하기 위한 요구사항 정의서다. 실제 이벤트 로깅 구현은 엔지니어링 팀과의 협의가 필요하다.*
