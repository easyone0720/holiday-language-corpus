import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager

from evaluate_validation import cohen_kappa, read

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
LABELS = ROOT / "data" / "labels" / "manual_labels_validation45.csv"
FIG = ROOT / "docs" / "figures"
VER = "v0.3"
PROMPT = "v0.3-presenter-rule"
EXPECTED_N = 788

TAXONOMY = {
    "종교·기원": ["예배·신학", "기원·역사해설"],
    "가정·사교·공동체": ["일상·사교형", "자선·나눔형"],
    "상업·소비": ["판촉·광고형", "상업화 비판·성찰형"],
    "시사·기타": ["시사·단신"],
}
CATS = list(TAXONOMY)
SUBS = [s for v in TAXONOMY.values() for s in v]
VALID_PAIRS = {(c, s) for c, subs in TAXONOMY.items() for s in subs}
CONFS = ["high", "medium", "low"]
# 4개 슬롯(파랑·주황·청록·노랑)은 인접 쌍 CVD·명도 검증을 통과한 순서. 청록·노랑은 대비가 낮아 조각 안에 % 라벨을 둔다
COLORS = dict(zip(CATS, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]))
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
VERSIONS = [("v0.1", "공식 기준선"), ("v0.2", "탐색적 보정"), ("v0.3", "탐색적 보정(검증 표본 관찰 후)")]
FONTS = ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR", "Noto Sans KR", "Noto Sans CJK SC"]


def pct(n, d):
    return round(100 * n / d, 1)


def period_label(p, n, newline=False):
    sep = "\n" if newline else " "
    return f"{p}{sep}(4 yrs, n={n})" if p == "1960–63" else f"{p}{sep}(n={n})"


def load():
    k = pd.read_csv(PROC / "kwic_snippets.csv", encoding="utf-8-sig")
    p = pd.read_csv(PROC / f"pred_full_{VER}.csv", encoding="utf-8-sig", keep_default_na=False)
    assert len(k) == EXPECTED_N, f"kwic_snippets {len(k)}행 (기대 {EXPECTED_N})"
    assert len(p) == EXPECTED_N, f"pred_full {len(p)}행 (기대 {EXPECTED_N})"
    assert k.snippet_id.is_unique and p.snippet_id.is_unique, "snippet_id 중복"
    assert not k.is_duplicate.any(), "중복 조각(is_duplicate)이 섞여 있음"
    df = k.merge(p, on="snippet_id", how="outer", validate="1:1", indicator=True)
    assert (df["_merge"] == "both").all(), "병합 시 한쪽에만 있는 snippet_id 존재"
    assert (df.status == "ok").all(), f"ok 아닌 행 {(df.status != 'ok').sum()}건"
    assert set(zip(df.category, df.sub_type)) <= VALID_PAIRS, "범주/세부 조합 오류"
    assert df.confidence.isin(CONFS).all(), "confidence 값 오류"
    assert set(df.prompt_version) == {PROMPT}, f"프롬프트 버전 혼재: {set(df.prompt_version)}"
    assert df.model.nunique() == 1, f"모델 혼재: {set(df.model)}"
    return df.drop(columns="_merge")


def overall(df):
    rows = []
    for sec, order in [("category", CATS), ("sub_type", SUBS), ("confidence", CONFS)]:
        vc = df[sec].value_counts()
        rows += [{"section": sec, "item": i, "n": int(vc.get(i, 0)), "pct": pct(vc.get(i, 0), len(df))} for i in order]
    return pd.DataFrame(rows)


def score(pred, lab):
    m = lab.merge(pred[["snippet_id", "category", "sub_type"]], on="snippet_id", how="left", validate="1:1")
    assert m.category.notna().all() and (m.category != "").all(), "라벨 표본에 예측이 없는 행"
    cm = pd.crosstab(m.human_category, m.category).reindex(index=CATS, columns=CATS, fill_value=0)
    return {
        "n": len(m),
        "category_accuracy_pct": pct((m.human_category == m.category).sum(), len(m)),
        "cohen_kappa": round(cohen_kappa(cm), 3),
        "sub_type_agreement_pct": pct((m.human_sub_type == m.sub_type).sum(), len(m)),
    }


def versions(df, lab):
    rows = []
    for v, role in VERSIONS:
        rows.append({"version": v, "role": role, "source": "검증 실행(45건)", **score(read(PROC / f"pred_validation_{v}.csv"), lab)})
    rerun = df[df.snippet_id.isin(lab.snippet_id)]
    rows.append({"version": VER, "role": "재실행(전체 코퍼스 실행 안의 45건)", "source": "pred_full", **score(rerun, lab)})
    return pd.DataFrame(rows)


def reproducibility(df):
    v = read(PROC / f"pred_validation_{VER}.csv")
    f = df.set_index("snippet_id").loc[v.snippet_id]
    rows = []
    for name, same in [
        ("category", f.category.values == v.category.values),
        ("sub_type", f.sub_type.values == v.sub_type.values),
        ("category+sub_type", (f.category.values == v.category.values) & (f.sub_type.values == v.sub_type.values)),
    ]:
        rows.append({
            "metric": name, "n": len(v), "n_match": int(same.sum()), "agreement_pct": pct(same.sum(), len(v)),
            "differing_ids": ";".join(v.snippet_id[~same]),
        })
    return pd.DataFrame(rows)


def period_category(df):
    rows = []
    for p in sorted(df.period.unique()):
        g = df[df.period == p]
        n = len(g)
        pg = g.page_id.value_counts()
        vc = g.category.value_counts()
        row = {"period": p, "period_label": period_label(p, n), "n": n, "n_pages": pg.size, "top_page_share": round(pg.iloc[0] / n, 3)}
        row.update({f"n_{c}": int(vc.get(c, 0)) for c in CATS})
        row.update({f"pct_{c}": pct(vc.get(c, 0), n) for c in CATS})
        rows.append(row)
    return pd.DataFrame(rows)


def page_level(df):
    rows = []
    for (p, pid), g in df.groupby(["period", "page_id"]):
        vc = g.category.value_counts()
        rows.append({
            "period": p, "page_id": pid, "date": g.date.iloc[0], "newspaper_title": g.newspaper_title.iloc[0], "n": len(g),
            **{f"pct_{c}": pct(vc.get(c, 0), len(g)) for c in CATS},
        })
    return pd.DataFrame(rows)


def page_mean(pooled, pages):
    rows = []
    for _, r in pooled.iterrows():
        g = pages[pages.period == r.period]
        for c in CATS:
            col = g[f"pct_{c}"]
            rows.append({
                "period_label": r.period_label, "category": c, "pooled_pct": r[f"pct_{c}"], "page_mean_pct": round(col.mean(), 1),
                "diff_pp": round(col.mean() - r[f"pct_{c}"], 1), "page_min_pct": col.min(), "page_max_pct": col.max(), "n_pages": len(g),
            })
    return pd.DataFrame(rows)


def period_crosstab(df, col, order):
    rows = []
    for p in sorted(df.period.unique()):
        g = df[df.period == p]
        vc = g[col].value_counts()
        row = {"period": p, "period_label": period_label(p, len(g)), "n": len(g)}
        row.update({f"n_{i}": int(vc.get(i, 0)) for i in order})
        row.update({f"pct_{i}": pct(vc.get(i, 0), len(g)) for i in order})
        rows.append(row)
    return pd.DataFrame(rows)


def set_font():
    have = {f.name for f in font_manager.fontManager.ttflist}
    for name in FONTS:
        if name in have:
            plt.rcParams["font.family"] = name
            plt.rcParams["axes.unicode_minus"] = False
            return name
    sys.exit(f"중단: 한글 폰트를 찾지 못함({', '.join(FONTS)} 중 하나 필요). 그림이 깨지므로 저장하지 않음")


def draw(table, path):
    fig, ax = plt.subplots(figsize=(10.5, 6.4), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    x = range(len(table))
    bottom = [0.0] * len(table)
    for c in CATS:
        vals = table[f"pct_{c}"].tolist()
        # 조각 사이 2px 표면색 간격
        ax.bar(x, vals, bottom=bottom, width=0.68, color=COLORS[c], edgecolor=SURFACE, linewidth=1, label=c)
        for i, v in enumerate(vals):
            if v >= 6:
                ax.text(i, bottom[i] + v / 2, f"{v:.0f}%", ha="center", va="center", fontsize=9.5,
                        color="white" if c == CATS[0] else INK)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xticks(list(x))
    ax.set_xticklabels([period_label(p, n, newline=True) for p, n in zip(table.period, table.n)], fontsize=10, color=INK)
    ax.set_ylim(0, 100)
    ax.set_yticks(range(0, 101, 20))
    ax.set_yticklabels([f"{t}%" for t in range(0, 101, 20)], color=MUTED, fontsize=9)
    ax.set_ylabel("범주별 비중", color=MUTED, fontsize=10)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c9c8c3")
    ax.tick_params(length=0)
    ax.yaxis.grid(True, color="#e6e5e1", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=4, frameon=False, fontsize=10, labelcolor=INK,
              handlelength=1.2, borderaxespad=-3.0)
    fig.suptitle(f"시기별 크리스마스 담론 4대 범주 비중 (전체 n={table.n.sum()})", x=0.06, y=0.985, ha="left", fontsize=14,
                 color=INK, fontweight="bold")
    fig.text(0.06, 0.02, f"분류: Claude Sonnet 5.5, 프롬프트 {PROMPT} (검증 표본을 관찰한 뒤 보정한 탐색적 버전). "
             "시기당 5개 신문 면에서 추출, 같은 면의 조각은 서로 독립이 아님.", fontsize=8.5, color=MUTED, ha="left")
    fig.subplots_adjust(left=0.07, right=0.97, top=0.84, bottom=0.17)
    fig.savefig(path, dpi=200, facecolor=SURFACE)
    plt.close(fig)


def show(title, frame):
    print(f"\n[{title}]")
    print(frame.to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="표와 그림을 파일로 저장(없으면 터미널 출력만)")
    a = ap.parse_args()

    df = load()
    print(f"무결성 통과: {len(df)}행 병합, 전부 ok, 프롬프트 {PROMPT}, 모델 {df.model.iloc[0]}")

    lab = read(LABELS)
    pooled = period_category(df)
    pages = page_level(df)
    tables = {
        "summary_overall": overall(df),
        "summary_versions": versions(df, lab),
        "summary_reproducibility": reproducibility(df),
        "summary_period_category": pooled,
        "sensitivity_page_level": pages,
        "sensitivity_page_mean": page_mean(pooled, pages),
        "summary_period_subtype": period_crosstab(df, "sub_type", SUBS),
        "summary_period_confidence": period_crosstab(df, "confidence", CONFS),
    }

    show("전체 분포 (범주·세부유형·신뢰도)", tables["summary_overall"])
    show("버전 비교 (검증 45건 기준, 공식 기준선은 v0.1)", tables["summary_versions"])
    show("재현성: 전체 실행 안의 45건 vs 검증 실행", tables["summary_reproducibility"])
    show("시기 × 범주 (%)", pooled[["period_label", "n", "n_pages", "top_page_share"] + [f"pct_{c}" for c in CATS]])
    sm = tables["sensitivity_page_mean"]
    show("민감도: 면 단위 평균 − 합산 비율(pp)", sm.pivot(index="period_label", columns="category", values="diff_pp")[CATS].reset_index())
    show("시기 × 신뢰도 (%)", tables["summary_period_confidence"][["period_label", "n"] + [f"pct_{c}" for c in CONFS]])
    print("\n※ v0.3 수치는 검증 표본을 관찰한 뒤 보정한 탐색적 결과이며 공식 기준선은 v0.1. 면 단위 표본(시기당 5면)이라 시기 간 차이는 기술적 비교로만 해석.")

    if not a.write:
        print("\n저장하지 않음(--write 없음)")
        return

    font = set_font()
    paths = {f"{name}_{VER}.csv": PROC / f"{name}_{VER}.csv" for name in tables}
    fig_path = FIG / f"period_category_share_{VER}.png"
    clash = [str(p) for p in [*paths.values(), fig_path] if p.exists()]
    if clash:
        sys.exit("중단: 이미 존재하는 파일이 있어 덮어쓰지 않음\n  " + "\n  ".join(clash))
    FIG.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(PROC / f"{name}_{VER}.csv", index=False, encoding="utf-8-sig", mode="x")
    draw(pooled, fig_path)
    print(f"\n저장 완료: CSV {len(tables)}개({PROC}), 그림 1개({fig_path}), 폰트 {font}")


if __name__ == "__main__":
    main()
