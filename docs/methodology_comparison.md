# 방법론 비교 분석

**작성일:** 2026-05-04

---

## 개요

동일한 시뮬레이션 데이터에서 4종 방법론을 적용했을 때 결론이 어떻게 달라지는지를 분석한다.

---

## 비교 대상

| 방법론 | 의사결정 기준 | 장점 | 한계 |
|---|---|---|---|
| Frequentist (z-test) | p < 0.05 | 업계 표준, 해석 명확, 재현성 높음 | 고정 표본 필요, peeking 취약 |
| Bayesian (Beta-Binomial) | P(B>A) > 0.95 | 작은 표본에서도 가능, 연속 모니터링 자연스러움, 기대 손실 제공 | 사전 분포 설정 민감, 주관성 논란 |
| Sequential (SPRT) | likelihood ratio 경계 도달 | 조기 종료로 트래픽 절약 | boundary 설정 복잡, rare-event 비율에서 수렴 느림 |
| Non-Inferiority (NIT) | CI가 NIM 이내 | 가드레일 판정에 적합, "약간의 악화는 허용"이라는 실용적 판단 | NIM 설정이 자의적이 될 위험 |

---

## 시뮬레이션 검증 결과

### 1. Peeking 팽창

**설정:** H0 true (효과 없음), 10,000회 시뮬레이션, 매 500명마다 p-value 확인

| Peek 시점 (n per group) | 누적 FP rate |
|---|---|
| 1,000 | 8.33% |
| 2,000 | 12.75% |
| 5,000 | 19.83% |
| 10,000 | **25.62%** |

Nominal alpha 5%에서 **5.1배 팽창**. 효과가 없는 실험에서도 4회 중 1회는 "효과가 있다"고 잘못 결론내리게 된다.

**실무 시사점:** 실험 기간 중 Primary metric의 p-value는 주 1회 이하로만 확인하고, 최종 판정은 사전 정의 기간 종료 후에만 수행해야 한다. 가드레일 모니터링은 별도 빈도로 수행 가능하나, Primary metric 판정에는 사용하지 않는다.

### 2. NIM 민감도

**설정:** bounce rate control=12.0%, treatment=12.5% (+0.5%p 악화), n=50,000/group

| NIM | 판정 | p-value |
|---|---|---|
| 0.5%p | INFERIOR | 0.5000 |
| 0.8%p | INFERIOR | 0.0740 |
| **0.84%p** | **Critical NIM** | — |
| 1.0%p | NON-INFERIOR | 0.0079 |
| 1.5%p | NON-INFERIOR | 0.0000 |

**Critical NIM = 0.84%p**: 이 값을 기준으로 출시 여부가 뒤집어진다.

**실무 시사점:** NIM 설정은 실험 전에 비즈니스 이해관계자와 합의해야 한다. 실험 후에 NIM을 조정하면 결과에 맞춰 기준을 바꾸는 p-hacking과 동일한 문제가 발생한다.

### 3. Frequentist vs Bayesian 불일치

**설정:** baseline=3.2%, n=50,000/group, effect size를 0.05%p~0.50%p까지 변화

effect 0.25%p에서 불일치 발생:
- Frequentist: p=0.079 → **비유의** (alpha=0.05 미달)
- Bayesian: P(B>A)=0.960 → **유의** (threshold=0.95 초과)

이 불일치가 발생하는 이유: Frequentist는 "관측된 효과가 우연에 의한 것일 확률"을 본다. Bayesian은 "현재 데이터를 고려했을 때 treatment이 더 나을 확률"을 본다. p=0.079는 "5% 기준에 아슬아슬하게 미달"이지만, 사후 확률 96%는 "treatment이 나을 가능성이 매우 높다"는 뜻이다.

**실무 시사점:** 경계 조건에서 Frequentist만으로 판단하면 의미 있는 효과를 놓칠 수 있다. Bayesian의 기대 손실(expected loss)을 보조 지표로 활용하면 "잘못된 선택의 비용"을 정량화할 수 있다.

### 4. Self-selection Bias

**설정:** true effect=+0.3%p, self-selection baseline shift=-0.5%p

| 추정 방법 | 효과 추정치 | Bias |
|---|---|---|
| RCT (랜덤 배정) | +0.19%p | — |
| Self-selection (실험실 토글) | +0.78%p | +0.59%p |

Self-selection은 true effect를 **4.0배 과대 추정**. 50회 시뮬레이션 평균 bias는 true effect의 **132%**에 해당.

**실무 시사점:** 에이블리 "실험실" 메뉴의 GIF 토글 데이터로 GIF 효과를 판단하는 것은 부적절하다. 인과적 효과를 측정하려면 랜덤 배정 기반 A/B 테스트로 전환해야 한다.

---

## 방법론 선택 가이드

| 상황 | 추천 방법론 | 이유 |
|---|---|---|
| Primary metric 최종 판정 | Frequentist + Bayesian 병행 | 업계 표준 + 경계 조건에서의 보완 |
| Guardrail metric 판정 | Non-Inferiority (NIT) | "약간의 악화는 허용"이라는 실용적 판단 가능 |
| 실험 기간 단축이 필요할 때 | Sequential (SPRT) | 단, CVR > 5% 이상이고 MDE > 1%p 이상일 때만 적합 |
| 자원이 제한적일 때 | Bayesian 단독 | 작은 표본에서도 의사결정 가능, 기대 손실로 비용 정량화 |
| 기존 A/B 플랫폼 호환 필요 | Frequentist 단독 | 대부분의 A/B 플랫폼이 Frequentist 기반 |

---

## SPRT의 한계 (본 프로젝트에서의 관찰)

SPRT는 per-observation log-likelihood ratio를 누적하여 결정 경계 도달 시 실험을 조기 종료하는 방법이다. 이론적으로는 효율적이나, 본 프로젝트의 시나리오에서는 한계가 관찰되었다.

### 수학적 원인

전환율 p = 0.032에서 per-observation log-LR을 계산하면:
- 전환 발생 시(outcome=1): log(p₁/p₀) = log(0.042/0.032) ≈ +0.27
- 전환 미발생 시(outcome=0): log((1-p₁)/(1-p₀)) ≈ -0.01

관측값의 96.8%가 0(미전환)이므로, 대부분의 관측에서 LR이 -0.01만큼 H0 방향으로 drift한다. 가끔 전환이 발생하면 +0.27로 H1 방향으로 점프하지만, 0과 1의 빈도 비율(96.8 : 3.2)에 의해 누적 LR이 H0 경계에 먼저 도달할 확률이 높아진다.

### 시뮬레이션 결과

CVR 3.2%, true effect +1.0%p(H1 true)에서 50,000 관측 쌍으로도 SPRT가 H0를 accept하는 결과가 관찰되었다. 이는 SPRT의 오류가 아니라 **rare-event 이항 비율에서 SPRT의 구조적 한계**이다.

### 적합 조건 가이드

| 조건 | SPRT 적합성 | 이유 |
|---|---|---|
| CVR ≥ 10%, MDE ≥ 2%p | 적합 | per-observation LR이 충분히 크고 양방향으로 균형 |
| CVR 5~10%, MDE ≥ 1%p | 조건부 적합 | 표본이 크면 수렴하지만 속도 이점이 줄어듦 |
| CVR < 5%, MDE < 1%p | **부적합** | 본 프로젝트의 시나리오. fixed-horizon 검정 권장 |

이커머스 A/B 테스트에서 CVR은 대부분 2~5% 범위이므로, SPRT보다 fixed-horizon Frequentist/Bayesian 검정이 실무적으로 더 적합하다. SPRT는 이메일 오픈율(20~30%), 버튼 클릭률(5~15%) 등 전환율이 높은 시나리오에서 효과적이다.

---

*본 분석에서 제시된 모든 수치는 `simulation/` 디렉토리의 코드로 재현 가능하다.*
