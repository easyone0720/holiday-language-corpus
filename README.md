# 크리스마스 말뭉치 분석 (Christmas Language Corpus Analysis: 1900–1963)

1900–1963 미국 신문 속 'Christmas' 담론의 시기별 변화와 LLM 분류·검증 | 20241229 이지원 · AI 활용 영미언어문화 데이터 분석

## 1. 연구 개요

1900–1963년 미국 신문 지면에 나온 `Christmas` 문맥을 분석해, 크리스마스 담론이 시간이 흐르며 일방적으로 상업화되었는지, 아니면 시기와 맥락에 따라 복합적으로 변동했는지 확인한다.

- **RQ1.** 시기별 4대 의미 범주(`종교·기원`, `가정·사교·공동체`, `상업·소비`, `시사·기타`)의 비중은 어떻게 변했는가?
- **RQ2.** 전 시기에 걸쳐 반복 등장하는 핵심 표현(`christmas day`, `christmas tree`)은 어떤 문맥에서 쓰였는가?

범위는 위 두 질문과 LLM 분류의 신뢰도 검증으로 한정한다. 토픽 모델링, 임베딩, 군집 분석은 하지 않았다.

## 2. 데이터 수집 및 전처리

| 항목 | 내용 |
| :-- | :-- |
| 출처 | 미 의회도서관 Chronicling America |
| 표집 | 35개 지면. 1900s~1950s는 10년 단위 각 5면, 1960–63은 아카이브 공개 상한(1963년) 때문에 4개년 5면. 7개 시기 |
| KWIC 추출 | 중심어 `Christmas` 앞뒤 30단어. 창이 겹치면 겹치는 위치를 건너뛰는 비중첩(`strict`) 방식 |
| 결과 | 독립 문맥 조각 788건 (1960–63은 `(4 yrs, n=71)`) |
| 원문 보존 | OCR 원문은 `snippet_raw`에 그대로 두고 철자를 고치지 않음. 정제본 `snippet_clean`은 노이즈 기호 제거, 줄 끝 하이픈 결합(뒤 글자가 소문자일 때만), 줄바꿈 공백 처리만 적용 |
| 분절 키워드 | 줄바꿈으로 갈라진 `Christ mas`도 히트로 잡음(`christ ?mas`). 중심어가 분절된 조각 42건 |
| 품질 점검 | 사전 단어 일치율 `dict_ratio` 계산(평균 0.916, 0.8 미만 30건). `rapidfuzz` 85% 기준 지면 간 복제 기사 검사에서 중복 0건 |
| 표본 분리 | 프롬프트 설계용 20건, 성능 검증용 45건을 한 번에 비복원 추출해 서로 겹치지 않음 |

시기별 조각 수는 1900s 137, 1910s 153, 1920s 114, 1930s 83, 1940s 88, 1950s 142, 1960–63 71(4 yrs)이다. 원본 JSON(`data/raw/`)은 `.gitignore`에 들어 있어 저장소에 올라가지 않는다.

## 3. LLM 분류 및 검증

### 분류 체계

- 4대 범주와 7개 세부유형: `일상·사교형`, `자선·나눔형`, `예배·신학`, `기원·역사해설`, `판촉·광고형`, `상업화 비판·성찰형`, `시사·단신`
- 조각마다 신뢰도(`high`, `medium`, `low`)와 판단 근거를 함께 출력
- 모델 `claude-sonnet-5-5`. 범주 정의와 경계 규칙은 `docs/category_definitions.md`

### 프롬프트 버전별 검증 (블라인드 정답 라벨 45건, `data/labels/manual_labels_validation45.csv`)

| 버전 | 규칙 | 정확도 | Cohen's $\kappa$ |
| :-- | :-- | --: | --: |
| v0.1 | 기본 프롬프트 | 88.9% | 0.786 |
| v0.2 | 경계 규칙 4종 추가 | 86.7% | 0.738 |
| **v0.3** | **행사 주관 주체 중심 재정의 (최종 공식 기준선)** | **91.1%** | **0.838** |

- v0.3의 $\kappa=0.838$은 Landis & Koch(1977) 구간에서 Almost Perfect(0.81–1.00)에 해당한다. v0.1은 0.786으로 Substantial(0.61–0.80)이다.
- $\kappa$는 `src/evaluate_validation.py`가 pandas 혼동행렬로 직접 계산한다. scikit-learn `cohen_kappa_score`로 같은 값이 나오는 것을 따로 확인했지만, 그 확인 스크립트와 scikit-learn은 저장소(`requirements.txt`)에 없다.
- v0.3 규칙은 v0.2의 오분류 사례를 검토한 뒤 정했으므로 45건 수치는 규칙 확정 시점의 일치도다. 전체 코퍼스 실행(`pred_full_v0.3.csv`)에 들어 있는 같은 45건은 93.3%($\kappa=0.876$)다.

### 4단계 검증

1. 정답 라벨 45건과 대조: 정확도 91.1%, $\kappa=0.838$
2. 같은 45건 재실행 일관성: 97.8%(44/45 일치, 불일치 S0507)
3. 저신뢰(`low`) 96건(12.2%)과 경계 사례의 원문 직접 검수
4. N-gram 표면 빈도와 LLM 문맥 분류의 교차 점검

신뢰도 분포는 high 431건(54.7%), medium 261건(33.1%), low 96건(12.2%)이다. low 비율은 1920s(28.1%)와 1940s(23.9%)에서 높고 1950s(4.9%)에서 낮다.

## 4. 주요 결과

### 전체 분포 (n=788)

| 범주 | 건수 | 비중 |
| :-- | --: | --: |
| 가정·사교·공동체 | 492 | 62.4% |
| 종교·기원 | 159 | 20.2% |
| 상업·소비 | 93 | 11.8% |
| 시사·기타 | 44 | 5.6% |

### RQ1. 시기별 범주 비중 (%)

| 시기 | n | 종교·기원 | 가정·사교·공동체 | 상업·소비 | 시사·기타 |
| :-- | --: | --: | --: | --: | --: |
| 1900s | 137 | 12.4 | 79.6 | 5.8 | 2.2 |
| 1910s | 153 | 16.3 | 69.9 | 11.1 | 2.6 |
| 1920s | 114 | 35.1 | 39.5 | 16.7 | 8.8 |
| 1930s | 83 | 8.4 | 71.1 | 16.9 | 3.6 |
| 1940s | 88 | 40.9 | 22.7 | 21.6 | 14.8 |
| 1950s | 142 | 10.6 | 81.7 | 7.0 | 0.7 |
| 1960–63 (4 yrs, n=71) | 71 | 26.8 | 50.7 | 8.5 | 14.1 |

세부유형 비중(시기별 전체 대비 %)과 원문 확인 결과는 다음과 같다.

| 시기 | 일상·사교형 | 자선·나눔형 | 예배·신학 | 기원·역사해설 |
| :-- | --: | --: | --: | --: |
| 1900s | 79.6 | 0.0 | 12.4 | 0.0 |
| 1910s | 62.7 | 7.2 | 15.7 | 0.7 |
| 1920s | 32.5 | 7.0 | 23.7 | 11.4 |
| 1930s | 71.1 | 0.0 | 8.4 | 0.0 |
| 1940s | 20.5 | 2.3 | 20.5 | 20.5 |
| 1950s | 80.3 | 1.4 | 10.6 | 0.0 |
| 1960–63 (4 yrs, n=71) | 46.5 | 4.2 | 21.1 | 5.6 |

- **상업·소비는 한 방향으로만 움직이지 않았다.** 1900s 5.8%에서 1940s 21.6%까지 늘었고(1920s→1930s는 +0.2%p 정체), 1950s에 7.0%로 내려갔다. 1930s~1940s의 상업·소비는 지역 상점의 연말 인사 광고가 중심이고, 1910s의 판촉·광고형 17건 중 16건은 1919-12-18 한 지면의 `CHRISTMAS SALE` 가격 목록이다. 1950s 상업·소비 10건 중 6건은 1958-12-26 신문 논평 한 편으로, 쇼핑 지출 증가를 짚으며 *"put Christ back into Christmas"*를 권한다.
- **일상·사교형이 대부분 시기의 기저다.** 1900s 79.6%, 1930s 71.1%, 1950s 80.3%. 1950s 114건은 지역 근황 칼럼(방문, 가족 모임, 클럽 모임)이 대부분이다.
- **1920s와 1940s의 종교·기원 상승(35.1%, 40.9%)**은 예배·신학과 함께 성탄 풍습의 유래를 다룬 `기원·역사해설`(11.4%, 20.5%)이 늘어난 결과다. 1940s의 예배·신학 18건 중 16건은 1949년 교회·미사 안내다.
- **1940s 시사·단신(14.8%, 13건)은 전쟁 보도가 아니다.** 단편소설, 'White Christmas' 노래 해설, 도서 소개, 퀴즈, 연말 전화 폭주 안내 같은 연말 읽을거리·공지다. 전쟁 관련 어휘가 든 조각은 88건 중 2건이며 둘 다 역사·노래 해설 문맥이다.
- **상업화 비판·성찰형 18건**의 시기별 분포는 1920s 10건, 1940s 1건, 1950s 6건, 1960–63 1건이다. 1920s는 대부분 '크리스마스 정신'을 다룬 칼럼이고 쇼핑·산업사회를 직접 말하는 글은 소수다. 18건 중 8건은 신뢰도 `low`다.

### 지면 단위 민감도

시기당 지면이 5개뿐이라 한 지면의 영향이 크다. 상업·소비 비중을 전체 조각 기준(pooled)과 지면별 비중의 평균(page mean)으로 비교했다(`data/processed/sensitivity_page_mean_v0.3.csv`).

| 시기 | pooled | page mean | 지면별 최소–최대 |
| :-- | --: | --: | --: |
| 1900s | 5.8 | 8.6 | 0.0–28.6 |
| 1910s | 11.1 | 20.0 | 0.0–100.0 |
| 1920s | 16.7 | 18.9 | 3.3–35.7 |
| 1930s | 16.9 | 26.2 | 0.0–100.0 |
| 1940s | 21.6 | 23.1 | 6.2–60.0 |
| 1950s | 7.0 | 7.9 | 0.0–25.9 |
| 1960–63 (4 yrs, n=71) | 8.5 | 8.6 | 0.0–26.7 |

지면 평균으로 보면 1910s 이후는 18.9~26.2% 사이에서 오르내리고 단조 증가는 아니다. 1940s 이후 하락(1950s 7.9%)은 두 방식에서 모두 나타난다.

### RQ2. 핵심 표현의 문맥

| 표현 | 조각 | 지면 | 종교·기원 | 가정·사교·공동체 | 상업·소비 | 시사·기타 |
| :-- | --: | --: | --: | --: | --: | --: |
| christmas day | 58 | 19 | 20.7% | 72.4% | 1.7% | 5.2% |
| christmas tree | 53 | 21 | 24.5% | 67.9% | 1.9% | 5.7% |
| christmas sale | 17 | 1 | 0.0% | 0.0% | 100.0% | 0.0% |

- `christmas day`와 `christmas tree`는 7개 시기 모두에 나타나고, 두 표현 모두 약 70%가 가정·공동체 행사 문맥, 20~25%가 예배·기원 해설 문맥이다. 비율은 전체 조각 기준이다.
- `christmas sale` 17건은 1910s의 한 지면(1919-12-18)에 모두 몰려 있다. 지면 수가 많은 표현과 한 면에 몰린 표현은 구분해서 읽어야 한다.

### 결론

1900년대부터 1940년대까지 상업·소비 담론이 늘어난 것은 사실이다(5.8%에서 21.6%). 그러나 전체 시기를 통틀어 지역 신문 속 크리스마스의 중심은 가족·이웃과 보내는 `가정·사교·공동체`(62.4%)와 예배·찬송·기원을 다룬 `종교·기원`(20.2%) 문맥이며, 상업·소비는 11.8%다. 1950s에는 상업·소비 비중이 다시 내려갔다. 단, 1920s와 1940s에는 종교·기원이 가정·사교보다 크거나 비슷해서(35.1% 대 39.5%, 40.9% 대 22.7%), 가정·사교 우세는 전체 기준에서 성립한다.

## 5. 한계점

- 표본이 작고(35면, 788조각) 지면이 시기당 5개라 특정 지역·신문의 영향이 크다.
- Chronicling America의 공개 범위 때문에 1963년이 상한이고, 1960–63은 4개년 표본이다.
- OCR 오탈자는 원문 보존 원칙에 따라 고치지 않았으므로 일부 조각의 분류 신뢰도가 낮다(`low` 96건).
- 검증용 정답 라벨은 45건이라 범주·세부유형별 일치율은 칸당 표본이 작다.

## 6. 저장소 구조

```
holiday-language-corpus/
├── README.md
├── requirements.txt
├── data/
│   ├── raw/                  원본 JSON (*_page.json, *_text.json). git 제외, 읽기 전용
│   ├── labels/
│   │   └── manual_labels_validation45.csv    수기 정답 라벨 45건
│   └── processed/
│       ├── kwic_snippets.csv                  KWIC 788건 (snippet_raw, snippet_clean)
│       ├── sample_design_20.csv, sample_validation_45.csv
│       ├── pred_validation_v0.1~v0.3.csv      검증 45건 분류 결과
│       ├── pred_full_v0.3.csv                 전체 788건 분류 결과
│       ├── eval_confusion_*.csv, eval_mismatches_*.csv
│       ├── summary_*_v0.3.csv                 전체·시기별·신뢰도·버전 비교·재현성 요약
│       ├── ngram_*_v0.3.csv                   N-gram 빈도·시기·범주·문맥
│       ├── discourse_*_v0.3.csv               공기어, 대표 용례, 저신뢰 사례, 지면 프로필
│       ├── sensitivity_page_*_v0.3.csv        지면 단위 민감도
│       ├── bias_adjusted_*.csv                지면 편향 보정 분석
│       └── deep_dive_contexts_v0.3.csv        심층 해석용 원문 317건
├── src/
│   ├── parse_and_clean.py              KWIC 추출·정제·중복 점검
│   ├── make_samples.py                 설계용·검증용 표본 추출
│   ├── classify_kwic.py                LLM 분류 (프롬프트 v0.1~v0.3)
│   ├── evaluate_validation.py          혼동행렬·Cohen's kappa
│   ├── analyze_corpus.py               전체·시기별 요약 표와 그림
│   ├── analyze_ngrams.py               N-gram × 범주 교차 점검
│   ├── extract_discourse_samples.py    공기어·대표 용례 추출
│   ├── analyze_page_bias_adjusted.py   지면 편향 보정 분석
│   ├── export_selected_ngram_contexts.py, inspect_ngram_contexts.py
│   ├── plot_subtype_comparison.py      세부유형 시기별 비교 그래프
│   ├── extract_deep_dive_contexts.py   심층 해석용 원문 추출
│   ├── generate_ppt_charts.py          발표용 차트
│   └── build_presentation.py           발표 자료(.pptx) 생성
├── docs/
│   ├── category_definitions.md         범주 정의서와 경계 규칙
│   ├── ai_usage_log.md                 AI 활용 기록
│   ├── ppt_outline_20p.md              20쪽 발표 구성안
│   ├── ppt_design_system.md            발표 자료 디자인 규격
│   └── figures/period_category_share_v0.3.png
├── outputs/
│   ├── christmas_discourse_presentation_20p.pptx
│   └── ppt_charts/                     발표용 차트 PNG
├── notebooks/, slides/                 비어 있음(.gitkeep)
```

`src/analyze.py`, `classify.py`, `clean.py`, `collect.py`, `docs/data_sources.md`, `notebooks/explore_categories.ipynb`는 내용이 없는 빈 파일이다. `outputs/christmas_discourse_presentation_20p.pptx`는 이전 구성안 기준으로 만든 것이며, 현재 `docs/ppt_outline_20p.md`를 반영해 다시 만들지 않았다.

## 7. 실행 방법

```bash
pip install -r requirements.txt
# 프로젝트 루트의 .env에 ANTHROPIC_API_KEY 설정

python src/parse_and_clean.py --write
python src/make_samples.py

# 검증 45건 분류와 평가
python src/classify_kwic.py --prompt-version v0.3-presenter-rule --input data/processed/sample_validation_45.csv --out data/processed/pred_validation_v0.3.csv
python src/evaluate_validation.py --pred data/processed/pred_validation_v0.3.csv --write

# 전체 788건 분류와 분석
python src/classify_kwic.py --prompt-version v0.3-presenter-rule --input data/processed/kwic_snippets.csv --out data/processed/pred_full_v0.3.csv --resume
python src/analyze_corpus.py --write
python src/analyze_ngrams.py --write
python src/extract_discourse_samples.py --write
python src/analyze_page_bias_adjusted.py --write

# 세부유형 비교 그래프와 심층 원문 추출
python src/plot_subtype_comparison.py --write
python src/extract_deep_dive_contexts.py
```

결과 파일을 쓰는 스크립트는 이미 있는 파일을 덮어쓰지 않고 중단한다(`--overwrite`가 있는 스크립트는 그 옵션으로만 갱신). `manual_labels_validation45.csv`는 수기 라벨이므로 스크립트가 다시 만들지 않는다.

## 8. AI 활용 기록

분류는 Claude Sonnet 5.5(`claude-sonnet-5-5`)로 했고, 코드 작성과 문서화에도 같은 모델을 썼다. 파일 생성·수정은 매번 분석자가 승인한 뒤에 했으며, 작업별 모델, 변경 파일, 판단 근거는 `docs/ai_usage_log.md`에 번호순으로 기록했다.
