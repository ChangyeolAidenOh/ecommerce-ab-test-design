# E-commerce A/B Test Experiment Design

패션 커머스 제품 실험에서 신규 기능을 출시해도 되는지 판단하기 위해, primary metric뿐 아니라 guardrail, self-selection bias, peeking risk, NIM 기반 비열등성 판단까지 포함한 **실험 의사결정 프레임워크**를 설계했다.

시뮬레이션으로 설계를 검증하고, ASOS Digital Experiments Dataset(NeurIPS 2021)의 78개 실제 A/B 테스트로 시뮬레이션에서 발견한 실험 운영 리스크가 실제 커머스 실험 데이터에서도 재현되는지 외부 타당도를 확인했다.

---

## Key Findings

| 발견 | 시뮬레이션 | ASOS 실제 데이터 |
|---|---|---|
| Peeking FP 팽창 | 25.6% (5.1x) | 22.2% (4.4x) |
| Self-selection bias | 4.0x 과대 추정 | — |
| Freq vs Bayes 불일치 구간 | p ≈ 0.079 | p = 0.057~0.083 |
| NIM 0.84%p에서 가드레일 판정 역전 | 확인 | — |
| 초반 결론 불안정 → 후반 안정화 | UNCONFIRMED → SAFE | 초반 23.5% → 후반 29.1% |

---

## Decision Framework

본 프로젝트는 p-value 하나로 출시 여부를 판단하지 않고, Primary metric, Guardrail, Bayesian posterior를 함께 고려해 다음 의사결정으로 연결한다.

| Primary | Guardrail (NIT) | Bayesian | Decision |
|---|---|---|---|
| 개선 (유의) | 비열등 통과 | posterior high | **Rollout** |
| 개선 (유의) | 비열등 미통과 | posterior high | **Limited rollout** — 세그먼트 제한 또는 추가 실험 |
| 불확실 (비유의) | 비열등 통과 | posterior moderate | **Extend** — 표본 추가 수집 |
| 불확실 (비유의) | 비열등 통과 | posterior low | **Discard** — 효과 없이 복잡성만 추가 |
| 악화 (유의) | 악화 | posterior low | **Stop** — 즉시 중단 |
| Freq/Bayes 불일치 | — | — | **Review** — 기대 손실 기반 보조 판단 |

Bayesian posterior 기준: high ≥ 95%, moderate 80~95%, low < 80%. Bayesian posterior는 p-value를 대체하는 단독 출시 기준이 아니라, p=0.05~0.08 경계 구간에서 기대 손실(expected loss)과 함께 보는 보조 판단 기준으로 사용했다.

---

## Motivation

패션 커머스 앱의 사용 흐름을 관찰하며, 유저가 직접 기능을 선택하는 구조와 개인화 리뷰 정렬 방식이 실험 설계 관점에서 어떤 편향을 만들 수 있는지 문제를 정의했다.

**Case 1 — GIF 피드 밀도:** 홈 피드의 GIF 자동재생을 유저가 직접 on/off하는 구조는 self-selection bias로 인해 인과적 효과 측정이 불가능하다. 시뮬레이션에서는 시각 피로에 민감한 유저가 GIF off를 선택하고 이 집단의 baseline CVR이 원래 낮은 구조를 가정했으며, 이 조건에서 self-selection은 실제 효과를 4.0배 과대 추정했다. 마켓플레이스 구조(셀러가 이미지를 직접 등록, 플랫폼은 피드 알고리즘만 통제 가능)를 반영하여 서버사이드 무작위 배정 기반 실험을 설계했다.

**Case 2 — 체형 리뷰 정렬:** 체형 필터(5cm/5kg 버켓)를 활성화해도 상품 목록의 "리뷰 많은순" 정렬은 전체 리뷰 수 기준이다. 정렬 기준을 "내 체형 리뷰 많은순"으로 변경하면 중간 순위 상품에서 의미 있는 재배치가 발생할 수 있다 (Spearman rho=0.82, top-20 overlap=90%). 정렬 변경이 단순 구매 전환뿐 아니라 탐색 행동의 어느 단계(상품 노출 → 리뷰 진입 → 장바구니 → 구매)에 영향을 주는지 funnel touchpoint 기록을 설계에 포함했다.

---

## Project Structure

```
ecommerce-ab-test-design/
├── docs/                                    # [1순위] 실험 설계서
│   ├── case1_gif_feed_density.md            #   Case 1: GIF 피드 밀도 실험
│   ├── case2_review_sort_order.md           #   Case 2: 체형 리뷰 정렬 실험
│   ├── methodology_comparison.md            #   4종 방법론 비교 분석
│   ├── simulation_parameter_basis.md        #   시뮬레이션 파라미터 근거
│   ├── external_validation.md              #   ASOS 데이터 외부 검증
│   └── event_logging_spec.md               #   이벤트 로깅 + 실험 마트 설계
│
├── sql/                                     # 실험 지표 집계 SQL
│   ├── create_experiment_mart.sql
│   ├── metric_session_cvr.sql
│   ├── guardrail_bounce_scroll.sql
│   └── segment_body_type.sql
│
├── simulation/                              # 설계 검증용 코드
│   ├── config.py
│   ├── data_generator.py
│   ├── power_analysis.py
│   ├── run_frequentist.py
│   ├── run_bayesian.py
│   ├── run_sequential.py
│   ├── run_non_inferiority.py
│   ├── guardrail_monitor.py
│   ├── bias_quantifier.py
│   ├── method_comparator.py
│   └── validate_with_asos.py
│
├── dashboard/                               # Streamlit 대시보드
│   └── app.py
│
├── figures/
├── data/                                    # ASOS 데이터셋 (gitignored)
├── requirements.txt
└── README.md
```

**산출물 위계:** 실험 설계서(docs) → 지표 집계 SQL(sql) → 방법론 검증 코드(simulation) → 의사결정 대시보드(dashboard)

---

## Quick Start

```bash
git clone https://github.com/ChangyeolAidenOh/ecommerce-ab-test-design.git
cd ecommerce-ab-test-design
pip install -r requirements.txt

# 시뮬레이션 실행
python -m simulation.data_generator
python -m simulation.power_analysis
python -m simulation.run_frequentist
python -m simulation.run_bayesian
python -m simulation.run_sequential
python -m simulation.run_non_inferiority
python -m simulation.guardrail_monitor
python -m simulation.bias_quantifier
python -m simulation.method_comparator

# ASOS 외부 검증 (data/ 폴더에 parquet 파일 필요)
python -m simulation.validate_with_asos

# Streamlit 대시보드
streamlit run dashboard/app.py
```

---

## Experiment Design Summary

### Case 1: GIF Feed Density

| 항목 | 내용 |
|---|---|
| 가설 | GIF 연속 노출 한도 3개 → CVR 감소 없음 |
| Primary | Session CVR |
| Guardrail | Bounce rate (NIM +1.0%p), Scroll depth (NIM -5%) |
| Variants | Control (무제한) / Treatment A (3개 한도) / Treatment B (2개 한도) |
| Sample size | 그룹당 68,388 (Bonferroni 보정) |
| Duration | 약 9일 (DAU 50,000, 50% 배정) |

### Case 2: Review Sort Order

| 항목 | 내용 |
|---|---|
| 가설 | 체형 리뷰 순 정렬 → CVR +0.5%p 이상 |
| Primary | CVR (체형 필터 유저) |
| Guardrail | 상품 노출 다양성 Gini (NIM +0.05), 탐색 포기율 (NIM +2.0%p) |
| Variants | Control (전체 리뷰 순) / Treatment (체형 리뷰 순) |
| Sample size | 그룹당 28,408 |
| Duration | 16일 + 반품 관찰 14일 = 30일 |

---

## Methodology

4종 방법론을 동일 데이터에서 비교:

| 방법론 | 용도 | 핵심 발견 |
|---|---|---|
| **Frequentist** (z-test) | Primary 판정 | 업계 표준, p < 0.05 기준 |
| **Bayesian** (Beta-Binomial) | Primary 보조 | p=0.05~0.08 경계에서 Frequentist와 불일치 |
| **Sequential** (SPRT) | 조기 종료 | CVR < 5% 환경에서 부적합 확인 |
| **Non-Inferiority** (NIT) | Guardrail 판정 | NIM 설정에 따라 출시 판정 역전 |

---

## External Validation

ASOS Digital Experiments Dataset(NeurIPS 2021)의 78개 실제 A/B 테스트로 외부 타당도를 검증했다. ASOS OCE Dataset은 글로벌 패션 이커머스 플랫폼에서 수행된 온라인 실험의 일별 누적 통계(count, mean, variance)를 포함한 공개 데이터셋으로, 본 프로젝트에서는 실험별 시간 누적 결과를 재구성해 peeking과 초기 결론 변동성을 점검했다.

ASOS 데이터는 제안 기능의 효과 검증이 아니라, **시뮬레이션에서 발견한 실험 운영 리스크가 실제 커머스 실험에서도 나타나는지** 확인하기 위한 외부 검증 데이터로 사용했다.

- Peeking 팽창: 시뮬레이션 25.6% ↔ 실제 22.2% **(일치)**
- Freq vs Bayes 불일치: p=0.057~0.083 구간에서 4건 **(일치)**
- 초반 결론 불안정: 24%가 3회 이상 뒤집힘 **(일치)**

---

## Data Sources

| 데이터 | 출처 | 용도 |
|---|---|---|
| 연령대 비율 | 와이즈앱·리테일 2025, 벤처스퀘어 2026.02 | 유저 풀 연령 분포 |
| 키/체중 평균 | KOSIS 건강검진통계 2024 (국민건강보험공단) | 유저 풀 체형 분포 |
| 체형 버켓 구조 | 패션 커머스 앱 스크린샷 | 5cm/5kg 버켓 정의 |
| 외부 검증 | ASOS OCE Dataset (NeurIPS 2021) | 방법론 외부 타당도 |

---

## Tech Stack

Python 3.10+ / scipy / statsmodels / numpy / pandas / matplotlib / plotly / streamlit / PostgreSQL (SQL spec)

---

## References

- Liu, C. H. Bryan et al., "Datasets for Online Controlled Experiments," NeurIPS 2021.
- KOSIS 국가통계포털, 건강검진통계 (국민건강보험공단, 2024).

---

**Independent Project** by Changyeol (Aiden) Oh
