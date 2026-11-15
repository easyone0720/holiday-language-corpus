import pandas as pd
from pathlib import Path

# 1. 통합 문맥 파일 로드
df = pd.read_csv("data/processed/ngram_contexts_v0.3.csv")

# ngram 컬럼 확인
ngram_col = "ngram" if "ngram" in df.columns else df.columns[1]

# 2. 분리 저장할 핵심 5개 표현
target_words = [
    "christmas day",
    "christmas tree",
    "merry christmas",
    "christmas sale",
    "christmas party",
]

out_dir = Path("data/processed")

for word in target_words:
    sub = df[df[ngram_col] == word].copy()
    safe_name = word.replace(" ", "_")
    out_path = out_dir / f"ngram_context_{safe_name}_v0.3.csv"
    sub.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {out_path} ({len(sub)}행)")