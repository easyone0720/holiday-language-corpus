import pandas as pd
from pathlib import Path

# 1. 정확한 경로의 파일 4종 직접 로드
inst = pd.read_csv("data/processed/ngram_instances_v0.3.csv")
freq = pd.read_csv("data/processed/ngram_frequency_v0.3.csv")
pred = pd.read_csv("data/processed/pred_full_v0.3.csv")
kwic = pd.read_csv("data/processed/kwic_snippets.csv")

# 컬럼명 자동 매칭
ngram_col = "ngram" if "ngram" in inst.columns else inst.columns[0]
id_col = "snippet_id" if "snippet_id" in inst.columns else ("id" if "id" in inst.columns else inst.columns[1])
pred_id = id_col if id_col in pred.columns else pred.columns[0]
kwic_id = id_col if id_col in kwic.columns else kwic.columns[0]

# 2. pred(분류 결과) + kwic(원문 전문) 병합
pred_cols = [c for c in pred.columns if c not in inst.columns or c == pred_id]
df = pd.merge(inst, pred[pred_cols], left_on=id_col, right_on=pred_id, how="left")

kwic_cols = [c for c in kwic.columns if c not in df.columns or c == kwic_id]
df = pd.merge(df, kwic[kwic_cols], left_on=id_col, right_on=kwic_id, how="left")

# 3. 상위 15개 N-gram + merry christmas 필터링
target_ngrams = freq[ngram_col].head(15).tolist()
if "merry christmas" not in target_ngrams and "merry christmas" in df[ngram_col].values:
    target_ngrams.append("merry christmas")

rank_map = {w: i for i, w in enumerate(target_ngrams, start=1)}
out_df = df[df[ngram_col].isin(target_ngrams)].copy()
out_df.insert(0, "ngram_rank", out_df[ngram_col].map(rank_map))

# 원문 텍스트 컬럼이 앞쪽에 오도록 정렬
kwic_text_cols = [c for c in kwic_cols if c != kwic_id]
front_cols = ["ngram_rank", ngram_col, id_col, "period", "year", "date", "category", "subtype", "confidence"] + kwic_text_cols + ["rationale"]
ordered_cols = list(dict.fromkeys([c for c in front_cols if c in out_df.columns]))
remaining_cols = [c for c in out_df.columns if c not in ordered_cols]
out_df = out_df[ordered_cols + remaining_cols]

sort_cols = [c for c in ["ngram_rank", "period", "category", id_col] if c in out_df.columns]
out_df = out_df.sort_values(sort_cols)

# 4. CSV 저장 및 첫 행 샘플 출력
out_path = Path("data/processed/ngram_contexts_v0.3.csv")
out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
print(f"저장 완료: {out_path} (총 {len(out_df)}행)")
print("포함된 컬럼:", list(out_df.columns))
print("\n--- 첫 번째 행 원문 샘플 확인 ---")
for col in ordered_cols:
    print(f"[{col}]: {out_df.iloc[0][col]}")