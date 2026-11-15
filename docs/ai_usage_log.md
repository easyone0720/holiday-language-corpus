# AI 활용 기록

- **사용 모델**: Claude Sonnet 5.5 (`claude-sonnet-5-5`)
- **연구 원칙**: 원본 코퍼스 읽기 전용 유지, OCR 오탈자 임의 교정 금지, 검증 표본 데이터 누수(leakage) 방지 및 모든 수정 전 연구자 승인 필수

## 1. 2026-11-15 오전 5시대 (KST) — 데이터 진단 및 파이프라인 초안 작성
- **생성·수정 파일**: 없음 (읽기 전용 진단, 임시 환경에서 dry-run 수행)
- **주요 내용**: `*_page` / `*_text` 원본 35쌍 구조 점검, OCR 노이즈 진단, KWIC 정제 코드 및 분류 프롬프트 초안 작성
- **판단 근거**: 원본 데이터 무결성을 위해 읽기 전용으로 점검하고, OCR 오탈자를 인위적으로 교정하지 않는 정제 순서를 설계함

## 2. 2026-11-15 오전 5시대 (KST) — 1·2단계 전처리 실행 및 표본 추출
- **생성·수정 파일**: `src/parse_and_clean.py`, `src/make_samples.py`, `src/classify_kwic.py`, `data/processed/kwic_snippets.csv`, `data/processed/sample_design_20.csv`, `data/processed/sample_validation_45.csv`, `data/labels/manual_labels_validation45.csv`, `docs/category_definitions.md`, 프로젝트 기획서(3.1 표본 규모 788조각 반영)
- **주요 내용**: 전체 788개 KWIC 조각 추출 및 정제, 설계용 표본(20건)과 검증용 표본(45건) 비복원 추출, 범주 정의서(코드북) 작성
- **판단 근거**: 비중첩(strict) 30단어 윈도우와 소문자 앞 하이픈 결합 규칙을 적용하고, 노이즈 기호(`* _ \ ~ { }`) 제거 범위를 확대함. 설계용과 검증용 표본을 한 번에 비복원 추출하여 표본 간 중복을 원천 차단함

## 3. 2026-11-15 오전 7시대 (KST) — 3단계 검증 환경 구축 및 다중 프롬프트 구조 구현
- **생성·수정 파일**: `src/classify_kwic.py`, `src/evaluate_validation.py`, `requirements.txt`, `CLAUDE.md`, 프로젝트 기획서(2.2, 4.2, 5.1, 5.2)
- **주요 내용**: 프롬프트 버전 선택(`v0.1-draft`, `v0.2-edge-rules`) 실행 옵션 구현, 혼동 행렬 및 Cohen's kappa 산출 평가 스크립트 작성
- **판단 근거**: 검증 표본에서 도출된 경계 규칙을 일반화(특정 상호명·OCR 예시 배제)하여 데이터 누수를 통제하고, 순수 기준선(`v0.1`)과 보정본(`v0.2`)을 모두 비교 보고할 수 있도록 재현 가능한 파이프라인을 구축함

## 4. 2026-11-15 오전 8시대 (KST) — API 호출 오류 진단 및 `.env` 환경변수 지원 반영
- **생성·수정 파일**: `src/classify_kwic.py`, `requirements.txt`(`python-dotenv` 추가)
- **주요 내용**: 초기 API 호출 실패 원인(SDK 시그니처 불일치 및 `temperature` 인자 오류) 진단 및 `.env` 자동 로드 반영
- **판단 근거**: 예측 파일의 `status` 로그 및 diff 분석으로 호출부 오류를 특정하고, 보안을 위해 `.env` 파일은 직접 열람하지 않는 원칙을 준수하여 수정 반영함

## 5. 2026-11-15 오전 9시대 (KST) — Sonnet 5.5 모델 제약 대응(`tool_choice` 및 `max_tokens` 수정)
- **생성·수정 파일**: `src/classify_kwic.py`
- **주요 내용**: `tool_choice`를 `auto`로 변경, `strict: True` 스키마 적용, `max_tokens` 4096 확대, 도구 호출 지시문 추가 및 미호출 응답 `CHECK` 기록 처리
- **판단 근거**: 공식 문서 확인 결과 `claude-sonnet-5-5`가 강제 `tool_choice` 및 기본값이 아닌 `temperature`를 400 오류로 거부하고 기본 thinking 토큰을 소비하므로, 호환성과 안정성을 확보하도록 호출 구조를 개선함

## 6. 2026-11-15 오전 9시대 (KST) — `v0.3-presenter-rule` 프롬프트 반영 및 AI 활용 기록 통합
- **생성·수정 파일**: `src/classify_kwic.py`(`v0.3-presenter-rule` 추가), `docs/ai_usage_log.md`
- **주요 내용**: `v0.1`·`v0.2` 예측 대조 후 행사 주관 주체(교회·주일학교 등 종교 기관 여부) 기준 `v0.3-presenter-rule` 추가 및 전체 AI 활용 기록 통합 정리
- **판단 근거**: 기존 프롬프트의 해시 불변성을 유지한 채 일반화된 주체 판정 규칙만 새 상수로 추가하고 `--dry-run` 검증을 마침. 검증 표본 재사용에 따른 낙관적 편향을 감안하여 `v0.1`을 공식 기준선, `v0.3`을 탐색적 개선 수치로 구분 보고하기로 확정함

## 7. 2026-11-15 오전 9시대 (KST) — v0.3 결과 대조 및 전체 코퍼스 분류용 `--resume` 패치
- **생성·수정 파일**: `src/classify_kwic.py`, `docs/ai_usage_log.md` (평가·코퍼스 CSV는 읽기 전용, 프로젝트 폴더에 새 파일 없음)
- **주요 내용**: S0045 라벨 수정 기준 재채점 결과(`v0.1` 88.9%, `v0.2` 86.7%, `v0.3` 91.1%)를 오답 목록과 대조해 `v0.3`의 신규 오답(S0507)과 개선 3건을 확인함. 전체 788건 일괄 분류를 위해 `--resume` 이어받기, 일시 오류 재시도 5회 확대, 50건 단위 진행 표시, 프롬프트·모델 불일치 방지, 중단 시 부분 결과 유지를 반영함. 모의 API로 중단·재개·버전 혼용 차단을 테스트함(실제 API 호출 없음)
- **판단 근거**: 788건 순차 호출 도중 실패하면 기존 코드는 부분 결과를 삭제해 처음부터 다시 해야 했음. 신뢰도는 검수 우선순위로 쓰되, 프롬프트를 조정한 45건에서 나온 결과이므로 `v0.1`을 공식 기준선, `v0.2`·`v0.3`을 탐색적 수치로 구분 보고함

## 8. 2026-11-15 오전 10시대 (KST) — 전체 코퍼스 788건 본분류 준비(`--resume` 동작 검증 및 실행 명령 정리)
- **생성·수정 파일**: 없음 (읽기 전용 확인, 임시 폴더에서 모의 API 테스트)
- **주요 내용**: 로컬 `src/classify_kwic.py`의 `--resume` 구현을 788건 규모 모의 API로 검증함(120번째 연속 실패 중단 → 부분 결과 보존 → 재개로 669건만 호출해 788건 완성, 중복·누락·BOM 중복 없음, 완료 파일 재실행 시 추가 호출 0건). 소요 시간 측정(10건)·본실행·재개 명령과 CHECK 행 검수 절차(재시도 후 잔여분은 `manual_labels_corpus_check.csv`에 별도 수기 라벨링)를 정리함
- **판단 근거**: 788건 순차 호출 중 중단돼도 결과를 잃지 않고 이어받는지 실제 호출 전에 확인해 API 비용과 재작업을 줄임. 전체 결과는 `v0.3`(탐색적 보정) 기준임을 보고 시 명시하기로 함

## 9. 2026-11-15 오전 10시대 (KST) — 전체 코퍼스 분석·시각화 스크립트(`analyze_corpus.py`) 초안 작성 및 검증
- **생성·수정 파일**: `src/analyze_corpus.py`(신규)
- **주요 내용**: `pred_full_v0.3.csv`와 `kwic_snippets.csv` 병합 무결성 검증(788행·전부 ok), 전체 분포·버전 비교(v0.1/v0.2/v0.3)·재현성 표, 시기×범주 집계(`n_pages`, `top_page_share`), 면 단위 민감도 표, 하위 유형·신뢰도 보조 표, 시기별 100% 누적 막대 그래프 구현. 임시 폴더에서 실제 데이터로 실행해 수치(v0.1 88.9%·kappa 0.786, v0.2 86.7%·0.738, v0.3 91.1%·0.838)와 덮어쓰기 방지·한글 폰트 처리를 검증한 뒤 승인받아 저장
- **판단 근거**: 점수는 하드코딩 없이 라벨·예측 파일에서 재계산하고, `--write` 없이는 저장하지 않으며 기존 파일은 덮어쓰지 않도록 설계함. v0.3 수치는 검증 표본 관찰 후 보정한 탐색적 결과이고, 시기당 5개 면 표본이라 같은 면의 조각이 독립이 아님을 그림 주석에 명시함

## 10. 2026-11-15 오후 1시대 (KST) — 질적 담론 분석용 추출 스크립트(`extract_discourse_samples.py`) 저장 및 의존성·기록 정리
- **생성·수정 파일**: `src/extract_discourse_samples.py`(신규), `requirements.txt`(`matplotlib` 추가, 누락돼 있던 `python-dotenv` 복원), `docs/ai_usage_log.md`
- **주요 내용**: 범주별·범주×시기 공기어(빈도·변별 순위), 대표 용례(칸당 2건, high 부족분은 medium으로 보충하고 `confidence` 열에 표시), low 신뢰도 목록·요약, 면별 프로필(범주 비중이 전체보다 30%p 이상 높은 면 표시)을 API 호출 없이 산출하는 스크립트를 임시 폴더에서 실제 데이터로 시험한 뒤 승인받아 저장함. 시험 중 low 신뢰도의 사전 일치율이 전체와 비슷하고(1940s는 시사·기타 13건 중 11건이 low), 표본 면이 몬태나 22·메인 8·미시시피 4·루이지애나 1임을 확인함
- **판단 근거**: 인명 필터는 사교란·방문객 명단 장르의 담론적 특징을 보존하기 위해 넣지 않았고, 대표 용례는 고정 시드 무작위 추출이라 대표성을 보장하지 않는 정독 출발점임을 출력에 명시함. `analyze_corpus.py`가 쓰는 `matplotlib`과 `classify_kwic.py`가 쓰는 `python-dotenv`가 의존성 목록에 없어 추가함

## 11. 2026-11-15 오후 2~3시대 (KST) — N-gram × 범주 일관성 점검 스크립트(`analyze_ngrams.py`) 저장 및 기획서 보완
- **생성·수정 파일**: `src/analyze_ngrams.py`(신규), `docs/ai_usage_log.md`(7~10번이 로컬 파일에 없어 함께 복원), 프로젝트_기획서_영어권명절언어_v4.md(§5.3·변경 이력 추가, claude.ai 프로젝트 문서)
- **주요 내용**: 기획서에 정의된 N-gram 분석 기준이 없음을 확인(과거 대화의 Google Books Ngram·COHA는 외부 코퍼스 예비 점검이었음)하고, 중심 `Christmas` 기준 2·3-gram의 빈도·시기별 출현·4대 범주·sub_type 7종 교차표·원문 역추적표(CSV 5종)를 산출하는 스크립트를 임시 폴더에서 실제 데이터로 시험한 뒤 승인받아 저장함. 트라이그램은 내용어만 허용, 그래프는 만들지 않음, `--anchor all` 옵션은 구현하지 않음
- **판단 근거**: 조각당 중심 히트 하나만 집계해 범주와 1:1로 대응시키고 구두점 경계를 넘는 조합은 만들지 않음. LLM이 n-gram이 포함된 문맥 전체를 보고 범주를 판정하므로 결과는 독립 증거가 아닌 일관성 점검(방법 검증 보조)으로 해석하고, 10건 미만 칸은 `small_n`으로 표시함. 기획서의 주 분석 범위(4대 범주 시기별 비율, 분류 신뢰도 검증)는 변경하지 않음

## 12. 2026-11-15 오후 10시대 (KST) — 지면 군집 편향 보정 분석(`analyze_page_bias_adjusted.py`) 작성 및 실행
- **생성·수정 파일**: `src/analyze_page_bias_adjusted.py`(신규), `data/processed/bias_adjusted_period_category.csv`, `bias_adjusted_ngram_period.csv`, `bias_adjusted_leave_extreme_out.csv`, `bias_adjusted_page_diversity.csv`(모두 신규, 기존 v0.3 산출물은 수정하지 않음)
- **주요 내용**: 실행 전에 입력 파일의 실제 열 구조를 확인하고, 재계산한 값이 `discourse_page_profile_v0.3.csv`·`summary_period_category_v0.3.csv`·`ngram_instances_v0.3.csv`와 일치하는지 단언문으로 검증함. 면 단위 범주 비율을 먼저 구한 뒤 시기별 평균·중앙값·표준편차(면 균등 가중)와 합산 비율과의 차이(`diff_pct`), n-gram별 TF·DF·집중도와 순위 비교, 극단 면 1·3·5개 제외(조각 수 기준·집중도 기준) 후 재집계, 면별 엔트로피 기반 다양성을 산출함. 예: `christmas sale` TF 17·DF 1, 1930s 종교·기원 합산 8.4% → 집중도 기준 5면 제외 시 28.0%
- **판단 근거**: 시기당 5개 면 표본이라 면 단위 표준편차·중앙값은 불안정하고, `ngram_instances_v0.3.csv`에는 선정된 29개 n-gram만 있음을 출력에 명시함. 극단 면 선정 기준과 지면 유형 임계값(0.9/0.6)은 AI가 정한 기본값이며 옵션으로 조정 가능. 연구자의 즉시 실행 요청에 따라 승인 전 실행했고, `--write`는 기존 파일을 덮어쓰지 않음

## 13. 2026-11-15 오후 10시대 (KST) — 20쪽 발표 구성안(`ppt_outline_20p.md`) 작성 및 저장
- **생성·수정 파일**: `docs/ppt_outline_20p.md`(신규), `docs/ai_usage_log.md`
- **주요 내용**: 지정된 요약·평가·N-gram·담론 파일에서 실제 수치와 `snippet_id`만 인용해 20쪽 슬라이드별 구성안(제목·본문·시각화·대본)을 작성하고 [AI]와 [연구자] 역할을 구분해 표기함. 연구자가 검토·승인한 뒤 저장함
- **판단 근거**: `1920s 상업화`는 데이터상 1920s~40s에 높고 1950s 이후 낮아지므로 직선적 상업화로 쓰지 않았고, v0.3 정확도(91.1%)는 검증 표본 관찰 후 보정된 탐색적 값이라 공식 기준선 v0.1(88.9%)과 함께 표기함. `year` 열이 없어 `date`로 대체했고, 지정 목록 밖의 `bias_adjusted_*.csv`는 7쪽·18쪽의 보조 근거로만 사용함

## 14. 2026-11-15 오후 10시대 (KST) — 발표용 차트 이미지 일괄 생성 스크립트(`generate_ppt_charts.py`) 작성 및 실행
- **생성·수정 파일**: `src/generate_ppt_charts.py`(신규), `outputs/ppt_charts/` 아래 PNG 9개(300 DPI, 신규): `slide05_period_counts.png`, `slide07_tf_vs_df.png`, `slide08_version_accuracy.png`, `slide09_overall_donut.png`, `slide10_top10_ngrams.png`, `slide12_period_category_stacked.png`, `slide13_ngram_category_mapping.png`, `slide16_low_confidence_by_period.png`, `slide18_leave_extreme_out.png`, `docs/ai_usage_log.md`
- **주요 내용**: `data/processed/`의 요약·N-gram·보정 분석 CSV를 읽기 전용으로 읽어 20쪽 구성안의 9개 슬라이드용 차트를 그림. 그리기 전에 시기 7개·788건·범주 비율 합 100%·`ngram_frequency`와 `bias_adjusted_ngram_period`의 TF 일치를 단언문으로 검증하고, 한글 폰트(Malgun Gothic 우선)를 찾지 못하면 중단하도록 함. `--write` 없이는 저장하지 않고 기존 파일은 덮어쓰지 않음. 결과 이미지를 직접 확인하며 겹친 라벨(18쪽 시작값, 16쪽 평균선)을 수정함
- **판단 근거**: 지정된 범주 팔레트는 색약 시뮬레이션에서 인접 색(주황·초록)이 가깝고 주황은 배경 대비가 낮아, 블록 안 수치 라벨·흰색 간격·범례를 함께 써서 색에만 의존하지 않게 함(주황 블록은 어두운 글씨). 8쪽은 v0.2·v0.3을 빗금으로 표시해 탐색적 결과임을 드러냄. 18쪽은 집중도·조각 수 기준 두 패널로 나눠 1930s 값이 기준에 따라 달라짐을 숨기지 않음(집중도 기준 5개 제외 후 남는 지면 1930s 2개). 1960–63은 `(4 yrs, n=71)`로 표기함. 이번 실행은 환경에 Malgun Gothic이 없어 NanumGothic으로 렌더링함(en 대시가 하이픈처럼 보임)

## 15. 2026-11-15 오후 10시대 (KST) — 발표용 차트 전면 개정(DF 표기 삭제·추이 차트 추가·빈티지 크리스마스 팔레트)
- **생성·수정 파일**: `src/generate_ppt_charts.py`(수정), `outputs/ppt_charts/` 아래 PNG 9개 갱신·신규(`slide05_period_counts.png`, `slide08_version_accuracy.png`, `slide09_overall_donut.png`, `slide10_top10_ngrams.png`, `slide12_period_category_stacked.png`, `slide13_ngram_category_mapping.png`, `slide13_top2_ngrams_period_trend.png`(신규), `slide16_low_confidence_by_period.png`, `slide18_leave_extreme_out.png`), `docs/ppt_outline_20p.md`(5·7·8·9·10·12·13·16·18쪽 시각화 안내와 변경 이력), `docs/ai_usage_log.md`
- **주요 내용**: 연구자 요청에 따라 모든 차트에서 `DF`(출현 지면 수) 표기를 삭제해 건수(n)·퍼센트(%)만 쓰고, 이에 따라 TF·DF 비교 차트(`slide07_tf_vs_df.png`)는 생성 목록에서 제외함. `christmas day`(n=58)·`christmas tree`(n=53)의 10년 단위 4대 범주 비율을 좌우 2단으로 비교하는 차트를 추가함(`ngram_instances_v0.3.csv`로 산출하고 `ngram_context_christmas_{day,tree}_v0.3.csv`의 시기×범주 건수와 일치함을 실행 시 확인, n<5인 시기는 흐리게 표시). 팔레트를 버건디 브라운·포레스트 그린·앤틱 골드·웜 토프 중심의 빈티지 크리스마스 톤으로 교체하고 어두운 회색 막대를 폐기함. 기존 파일 갱신을 위해 `--overwrite` 옵션을 추가하고(기본은 덮어쓰기 금지 유지), `--transparent` 옵션을 추가함
- **판단 근거**: 지정 4색 범주 팔레트는 검증 스크립트에서 채도·색각이상(적록)·보통시력 구분(앤틱 골드↔웜 토프 ΔE 13) 기준 FAIL이어서, 색을 바꾸지 않고 블록 안 수치 라벨·흰색 간격·범례로 색 의존을 줄임(앤틱 골드 블록은 코코아 글씨, 대안 토프 `#6F665E`는 구분 기준 통과). `slide18_leave_extreme_out.png`는 요청 목록에 없었지만 18쪽에서 쓰이고 DF 표기가 없어 새 팔레트로 함께 갱신함. 구성안 7·10쪽 본문에는 DF 언급이 남아 있어 연구자 결정 대기. 이번 실행도 Malgun Gothic이 없는 환경이라 NanumGothic으로 렌더링함

## 16. 2026-11-15 오후 11시대 (KST) — 발표용 차트 형태 다변화(롤리팝·기울기·산점도·영역·히트맵) 및 구성안 매핑 갱신
- **작업 모델**: claude-sonnet-5-5 (Claude Sonnet 5.5)
- **생성·수정 파일**: `src/generate_ppt_charts.py`(수정), `outputs/ppt_charts/` 아래 PNG 갱신·신규: `slide05_period_counts.png`(갱신, 롤리팝), `slide08_version_slope.png`(신규), `slide09_overall_donut.png`(갱신, 중앙 "총 788건"), `slide10_ngram_scatter.png`(신규), `slide12_period_category_area.png`(신규), `slide13_subtype_heatmap.png`(신규), `slide13_top2_ngrams_period_trend.png`(갱신, 제목·부제 간격 수정), `slide16_validation_summary.png`(신규), `slide18_leave_extreme_out.png`(갱신), `docs/ppt_outline_20p.md`(시각화 줄·변경 이력·7·10쪽 본문의 DF 표기를 "등장한 신문 지면 수"로 수정), `docs/ai_usage_log.md`
- **주요 변경 사항**: 5·8·10·12·13·16쪽 차트를 주제에 맞는 형태로 교체. 8쪽 재현율은 `eval_confusion_v0.{1,2,3}-*.csv`에서 직접 계산(4/8 → 3/8 → 6/8건). 10쪽 지면 수는 `ngram_instances_v0.3.csv`의 `page_id`에서 계산. 12쪽은 시기 사이를 선으로 이은 영역이며 보간 곡선은 쓰지 않음. 13쪽 히트맵은 `summary_period_subtype_v0.3.csv`와 `pred_full_v0.3.csv`의 세부유형→범주 대응 일치를 확인한 뒤 작성.
- **판단 근거**: 요청 문서의 "재현율 0.50 → 0.75"에는 중간 값(v0.2 0.375)이 있어 함께 표시하고, 8건 기준이라 방향만 참고하도록 주석을 붙임. 16쪽의 low 비중은 "맥락 혼재의 입증"이 아니라 단서로만 표현함. 요청 목록에 없던 `slide18`은 구성안 18쪽에서 쓰므로 유지. 기존 `slide08_version_accuracy.png`, `slide10_top10_ngrams.png`, `slide12_period_category_stacked.png`, `slide13_ngram_category_mapping.png`, `slide16_low_confidence_by_period.png`, `slide07_tf_vs_df.png`는 더 이상 생성되지 않으며 삭제는 연구자가 수행함.
- **검증**: 시기 7개·788건, 세부유형 합계와 범주 비율 일치, 혼동행렬 정확도가 `summary_versions_v0.3.csv`와 일치, 상위 표현 건수 일치를 실행마다 확인함. 한글 폰트는 샌드박스의 Noto Sans CJK KR로 렌더링했으며 Windows에서 Malgun Gothic으로 다시 그리려면 `--overwrite`가 필요함.
