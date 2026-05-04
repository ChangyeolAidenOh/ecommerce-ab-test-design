# E-commerce A/B Test Experiment Design

에이블리 앱 직접 사용 관찰에서 출발한 **A/B 테스트 실험 설계 프로젝트**.

시뮬레이션 기반으로 실험을 설계하고, 4종 방법론을 비교하며, 글로벌 패션 이커머스(ASOS)의 실제 A/B 테스트 데이터로 방법론을 검증했다.

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

## Motivation

에이블리 앱(iOS v2.364.0)을 직접 사용하면서 두 가지 문제를 발견했다.

**Case 1 — GIF 피드 밀도:** 홈 피드의 GIF 자동재생을 "실험실" 메뉴에서 유저가 직접 on/off하는 구조는 self-selection bias로 인해 인과적 효과 측정이 불가능하다. 시뮬레이션 결과, self-selection은 실제 효과를 4.0배 과대 추정했다.

**Case 2 — 체형 리뷰 정렬:** 체형 필터(5cm/5kg 버켓)를 활성화해도 상품 목록의 "리뷰 많은순" 정렬은 전체 리뷰 수 기준이다. 정렬 기준을 "내 체형 리뷰 많은순"으로 변경하면 중간 순위 상품에서 의미 있는 재배치가 발생할 수 있다 (Spearman rho=0.82, top-20 overlap=90%).

두 시나리오 모두 에이블리의 마켓플레이스 구조(셀러가 이미지를 직접 등록, 에이블리는 피드 알고리즘만 통제 가능)를 반영한 설계다.

---

## Project Structure

```
ecommerce-ab-test-design/
├── docs/                                    # [1순위] 실험 설계서
│   ├── case1_gif_feed_density.md            #   Case 1: GIF 피드 밀도 실험
│   ├── case2_review_sort_order.md           #   Case 2: 체형 리뷰 정렬 실험
│   ├── methodology_comparison.md            #   4종 방법론 비교 분석
│   ├── simulation_parameter_basis.md        #   시뮬레이션 파라미터 근거
│   └── external_validation.md              #   ASOS 데이터 외부 검증
│
├── simulation/                              # [3순위] 설계 검증용 코드
│   ├── config.py                            #   실험 파라미터 중앙 관리
│   ├── data_generator.py                    #   합성 데이터 + 절대수의 법칙 검증
│   ├── power_analysis.py                    #   표본 크기 / MDE / 검정력
│   ├── run_frequentist.py                   #   빈도주의 검정
│   ├── run_bayesian.py                      #   베이지안 AB 검정
│   ├── run_sequential.py                    #   순차 검정 + Peeking 시뮬레이션
│   ├── run_non_inferiority.py               #   비열등성 검정 + NIM 민감도
│   ├── guardrail_monitor.py                 #   가드레일 모니터링
│   ├── bias_quantifier.py                   #   Self-selection bias 정량화
│   ├── method_comparator.py                 #   4종 방법론 교차 비교
│   └── validate_with_asos.py               #   ASOS 데이터 외부 검증
│
├── dashboard/                               # [4순위] Streamlit 대시보드
│   └── app.py
│
├── figures/                                 # 시각화 산출물
├── data/                                    # ASOS 데이터셋 (gitignored)
├── requirements.txt
└── README.md
```

**산출물 위계:** 설계서(docs) > 시각화(figures) > 코드(simulation) > 대시보드(dashboard)

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

ASOS Digital Experiments Dataset (NeurIPS 2021)의 78개 실제 A/B 테스트로 시뮬레이션 발견을 검증:

- Peeking 팽창: 시뮬레이션 25.6% ↔ 실제 22.2% **(일치)**
- Freq vs Bayes 불일치: p=0.057~0.083 구간에서 4건 **(일치)**
- 초반 결론 불안정: 24%가 3회 이상 뒤집힘 **(일치)**

---

## Data Sources

| 데이터 | 출처 | 용도 |
|---|---|---|
| 연령대 비율 | 와이즈앱·리테일 2025, 벤처스퀘어 2026.02 | 유저 풀 연령 분포 |
| 키/체중 평균 | KOSIS 건강검진통계 2024 (국민건강보험공단) | 유저 풀 체형 분포 |
| 체형 버켓 구조 | 에이블리 앱 스크린샷 (v2.364.0) | 5cm/5kg 버켓 정의 |
| 외부 검증 | ASOS OCE Dataset (NeurIPS 2021) | 방법론 외부 타당도 |

---

## Tech Stack

Python 3.10+ / scipy / statsmodels / numpy / pandas / matplotlib / plotly / streamlit

외부 과금 서비스 없음. MacBook Pro M2 (16GB) 로컬 실행.

---

## References

- Liu, C. H. Bryan et al., "Datasets for Online Controlled Experiments," NeurIPS 2021.
- KOSIS 국가통계포털, 건강검진통계 (국민건강보험공단, 2024).
- 에이블리 DA 블로그, "서비스 그 이면의 숫자들," 2025.02.

---

**Independent Project** by Changyeol (Aiden) Oh
