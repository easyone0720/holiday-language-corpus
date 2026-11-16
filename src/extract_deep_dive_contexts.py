"""심층 해석용 원문 전문을 뽑아 data/processed/deep_dive_contexts_v0.3.csv로 저장한다.

- 읽기 전용: pred_full_v0.3.csv와 kwic_snippets.csv는 읽기만 한다. 원문 철자는 고치지 않는다(OCR 그대로).
- 병합 키: snippet_id. 병합 뒤 행 수(788)와 범주·세부유형 건수를 검증한다.
- 선택 규칙(selection_reason, 한 조각이 여러 규칙에 걸리면 ' | '로 이어 붙임):
  ① 상업·소비 전체(93건), 그중 상업화 비판·성찰형 전수(18건)와 판촉·광고형(75건)
  ② 1920s·1940s·1950s의 기원·역사해설, 상업화 비판·성찰형, 판촉·광고형, 시사·단신, 일상·사교형
- 저장 파일이 이미 있으면 덮어쓰지 않고 중단한다(--overwrite로만 갱신).
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = PROC / "deep_dive_contexts_v0.3.csv"
KEY_PERIODS = ["1920s", "1940s", "1950s"]
KEY_SUBS = ["기원·역사해설", "상업화 비판·성찰형", "판촉·광고형", "시사·단신", "일상·사교형"]
COLS = ["snippet_id", "period", "date", "category", "sub_type", "snippet_clean", "confidence", "place", "page_id", "selection_reason"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args()
    if OUT.exists() and not a.overwrite:
        sys.exit(f"중단: 이미 있는 파일이라 덮어쓰지 않음(갱신하려면 --overwrite): {OUT}")
    pred = pd.read_csv(PROC / "pred_full_v0.3.csv", encoding="utf-8-sig")
    kwic = pd.read_csv(PROC / "kwic_snippets.csv", encoding="utf-8-sig")
    df = pred.merge(kwic[["snippet_id", "period", "date", "place", "page_id", "snippet_clean"]], on="snippet_id", how="left", validate="one_to_one")
    assert len(df) == 788 and df.snippet_clean.notna().all()
    assert (df.category == "상업·소비").sum() == 93 and (df.sub_type == "상업화 비판·성찰형").sum() == 18 and (df.sub_type == "판촉·광고형").sum() == 75

    reasons = {sid: [] for sid in df.snippet_id}
    for r in df.itertuples():
        if r.category == "상업·소비":
            reasons[r.snippet_id].append(f"상업·소비 전체({r.sub_type})")
        if r.period in KEY_PERIODS and r.sub_type in KEY_SUBS:
            reasons[r.snippet_id].append(f"{r.period} {r.sub_type}")
    df["selection_reason"] = df.snippet_id.map(lambda s: " | ".join(reasons[s]))
    out = df[df.selection_reason != ""][COLS].sort_values(["date", "snippet_id"]).reset_index(drop=True)
    out["snippet_clean"] = out["snippet_clean"].astype(str)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"저장: {OUT} ({len(out)}행)")
    print(out.groupby(["period", "sub_type"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
