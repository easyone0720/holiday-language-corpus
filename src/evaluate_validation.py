import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CATS = ["종교·기원", "가정·사교·공동체", "상업·소비", "시사·기타"]


def read(path):
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    return df.apply(lambda c: c.str.strip())  # 공백은 메모리에서만 정리하고 원본 파일은 건드리지 않음


def cohen_kappa(cm):
    n = cm.values.sum()
    po = cm.values.trace() / n
    pe = (cm.sum(axis=1).values * cm.sum(axis=0).values).sum() / n ** 2
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def write_new(frame, path, index=False):
    with open(path, "x", encoding="utf-8-sig", newline="") as f:  # 이미 있으면 예외
        frame.to_csv(f, index=index)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True, help="예: data/processed/pred_validation_v0.1.csv")
    ap.add_argument("--labels", default=str(ROOT / "data/labels/manual_labels_validation45.csv"))
    ap.add_argument("--samples", default=str(ROOT / "data/processed/sample_validation_45.csv"))
    ap.add_argument("--write", action="store_true", help="혼동 행렬과 오답 노트를 CSV로 저장")
    a = ap.parse_args()

    pred, hum, smp = read(a.pred), read(a.labels), read(a.samples)
    bad = pred[pred.status != "ok"]
    if len(bad):
        print(f"경고: status가 ok가 아닌 {len(bad)}건은 채점에서 제외 {list(bad.snippet_id)}")
    missing = set(hum.snippet_id) - set(pred.snippet_id)
    if missing:
        print(f"경고: 예측이 없는 ID {sorted(missing)}")

    df = (hum.merge(pred[pred.status == "ok"], on="snippet_id")
             .merge(smp[["snippet_id", "snippet_clean"]], on="snippet_id"))
    if df.empty:
        sys.exit("채점할 행이 없습니다")

    n = len(df)
    hit = df.human_category == df.category
    cm = pd.crosstab(df.human_category, df.category).reindex(index=CATS, columns=CATS, fill_value=0)
    ver = df.prompt_version.iloc[0]

    print(f"프롬프트 {ver} | 채점 n={n}/{len(hum)}")
    print(f"category 일치율 {hit.mean():.1%} ({hit.sum()}/{n}), Cohen's kappa {cohen_kappa(cm):.3f}")
    print(f"sub_type 일치율 {(df.human_sub_type == df.sub_type).mean():.1%} (참고용: 칸당 표본이 작아 해석 주의)")
    print("\n혼동 행렬 (행=연구자, 열=Claude)")
    print(cm.to_string())
    recall = cm.values.diagonal() / cm.sum(axis=1).replace(0, float("nan")).values
    print("연구자 라벨 기준 재현율:", {c: round(float(r), 2) for c, r in zip(CATS, recall)})

    miss = df.loc[~hit, ["snippet_id", "human_category", "category", "human_sub_type", "sub_type",
                          "confidence", "rationale", "memo", "snippet_clean"]].copy()
    miss["snippet_clean"] = miss.snippet_clean.str.slice(0, 200)
    print(f"\n불일치 {len(miss)}건 (오답 노트)")
    print(miss.to_string(index=False))

    if a.write:
        out = ROOT / "data" / "processed"
        targets = [out / f"eval_confusion_{ver}.csv", out / f"eval_mismatches_{ver}.csv"]
        if any(t.exists() for t in targets):
            sys.exit("중단: 같은 프롬프트 버전의 평가 파일이 이미 있습니다(덮어쓰기 금지)")
        write_new(cm, targets[0], index=True)
        write_new(miss, targets[1])
        print("저장:", *targets)


if __name__ == "__main__":
    main()
