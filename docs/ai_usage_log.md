# AI 활용 기록

작업 시각(KST)·모델·변경 파일·판단 근거를 시간순으로 적는다.

## 초기 작업 (시각·내용 보충 예정)

| # | 일시(KST) | 모델 | 파일 | 주요 변경 및 판단 근거 |
|---|---|---|---|---|
| A | 2026-11-15 ( ) | ( ) | 프로젝트 폴더 변경 없음(읽기 전용) | 데이터 현황·쌍(pair) 점검, full_text 노이즈 진단 |
| B | 2026-11-15 ( ) | ( ) | src/parse_and_clean.py, src/make_samples.py, data/processed/kwic_snippets.csv, sample_design_20.csv, sample_validation_45.csv, data/labels/manual_labels_validation45.csv | 정제·KWIC 추출 코드 저장 및 실행, 설계 20·검증 45 표본 분리 |
| C | 2026-11-15 ( ) | ( ) | docs/category_definitions.md | 4대 범주·sub_type 정의, 경계 규칙 |
| D | 2026-11-15 ( ) | ( ) | src/classify_kwic.py(최초 저장) | 분류 스크립트 초안 저장(API 실행 보류) |

## 2026-11-15 작업 기록

| # | 일시(KST) | 모델 | 파일 | 주요 변경 및 판단 근거 |
|---|---|---|---|---|
| 1 | 2026-11-15 7시대 | Claude Sonnet 5.5 (claude-sonnet-5-5) | 프로젝트 폴더 변경 없음 | 임시 폴더에서 evaluate_validation.py 가짜 예측 테스트. 라벨 파일은 무변경으로 읽기만 수행. 일반화 방안과 평가 순서 대안 제시 |
| 2 | 2026-11-15 7시대 | Claude Sonnet 5.5 (claude-sonnet-5-5) | src/classify_kwic.py(수정), src/evaluate_validation.py, requirements.txt(신규 내용), CLAUDE.md, 프로젝트_기획서 | API 키 부재로 파일럿 보류, 다중 프롬프트 선택 구조 구현 |
| 3 | 2026-11-15 8시대 | Claude Sonnet 5.5 (claude-sonnet-5-5) | 프로젝트 폴더 변경 없음 | 예측 파일 status와 diff 분석으로 SDK 시그니처 원인 특정 |
| 4 | 2026-11-15 8시대 | Claude Sonnet 5.5 (claude-sonnet-5-5) | src/classify_kwic.py(덮어쓰기), requirements.txt(python-dotenv 추가) | 승인된 수정안 반영, .env는 열람하지 않는 원칙 준수 |
| 5 | 2026-11-15 9시대 | Claude Sonnet 5.5 (claude-sonnet-5-5) | 프로젝트 폴더 변경 없음 | 공식 문서 확인 후 forced tool_choice, temperature, thinking 제약을 모의 테스트 |
| 6 | 2026-11-15 9시대 | Claude Sonnet 5.5 (claude-sonnet-5-5) | src/classify_kwic.py(수정) | tool_choice를 auto로 변경, strict 추가, max_tokens 4096 확대, 도구 호출 지시문 추가, 도구 호출이 없으면 CHECK 기록 |
| 7 | 2026-11-15 9시대 | Claude Sonnet 5.5 (claude-sonnet-5-5) | 프로젝트 폴더 변경 없음(pred·eval CSV는 읽기 전용) | v0.1/v0.2 예측 대조(category 차이는 S0729 1건), v0.3 프롬프트 초안 제안 |
| 8 | 2026-11-15 9시대 | Claude Sonnet 5.5 (claude-sonnet-5-5) | src/classify_kwic.py(v0.3-presenter-rule 추가), docs/ai_usage_log.md(신규 내용) | 주관 주체 기준 규칙 추가(고유명사·조각 ID 없음, S0362 전용 예외 없음). v0.3 수치는 검증 표본을 관찰한 뒤 보정한 탐색적 수치이며 공식 기준선은 v0.1(86.7%, kappa 0.749) |
