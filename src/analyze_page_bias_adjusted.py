import argparse
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
VER = "v0.3"
PROMPT = "v0.3-presenter-rule"
EXPECTED_N = 788
EXPECTED_PAGES = 35
CATS = ["종교·기원", "가정·사교·공동체", "상업·소비", "시사·기타"]
OUT_NAMES = [
    "bias_adjusted_period_category.csv",
    "bias_adjusted_ngram_period.csv",
    "bias_adjusted_leave_extreme_out.csv",
    "bias_adjusted_page_diversity.csv",
]


def pct(x, d=1):
    return round(100 * x, d)


def need(df, cols, name):
    miss = [c for c in cols if c not in df.columns]
    if miss:
        sys.exit(f"중단: {name}에 필요한 열이 없음: {miss} (실제 열: {list(df.columns)})")


def read(name, **kw):
    return pd.read_csv(PROC / name, encoding="utf-8-sig", keep_default_na=False, **kw)


def period_label(p, n):
    return f"{p} (4 yrs, n={n})" if p == "1960–63" else f"{p} (n={n})"


def load():
    k = read("kwic_snippets.csv")
    p = read(f"pred_full_{VER}.csv")
    prof = read(f"discourse_page_profile_{VER}.csv")
    inst = read(f"ngram_instances_{VER}.csv")
    summ = read(f"summary_period_category_{VER}.csv")
    need(k, ["snippet_id", "page_id", "period", "date", "place"], "kwic_snippets.csv")
    need(p, ["snippet_id", "category", "status", "prompt_version"], f"pred_full_{VER}.csv")
    need(prof, ["page_id", "period", "date", "place", "n"] + [f"pct_{c}" for c in CATS], f"discourse_page_profile_{VER}.csv")
    need(inst, ["ngram", "snippet_id", "period", "page_id", "category"], f"ngram_instances_{VER}.csv")
    need(summ, ["period"] + [f"pct_{c}" for c in CATS], f"summary_period_category_{VER}.csv")

    assert len(k) == EXPECTED_N and len(p) == EXPECTED_N, f"행 수 불일치: kwic {len(k)}, pred {len(p)}"
    assert (p.status == "ok").all() and set(p.prompt_version) == {PROMPT}, "예측 파일 상태·프롬프트 버전 불일치"
    # 열을 먼저 고르고 병합해서 중복 열(_x, _y)이 생기지 않게 한다
    d = k[["snippet_id", "page_id", "period", "date", "place"]].merge(p[["snippet_id", "category"]], on="snippet_id", how="outer", validate="1:1", indicator=True)
    assert (d["_merge"] == "both").all() and d.category.isin(CATS).all(), "병합 누락 또는 알 수 없는 범주"
    d = d.drop(columns="_merge")

    cnt = pd.crosstab(d.page_id, d.category).reindex(columns=CATS, fill_value=0)
    pages = d.groupby("page_id").agg(period=("period", "first"), date=("date", "first"), place=("place", "first")).join(cnt)
    pages["n"] = cnt.sum(axis=1)
    assert len(pages) == EXPECTED_PAGES and pages.groupby("period").size().eq(5).all(), "면 수가 기대와 다름"

    # 기존 산출물과 다시 계산한 값이 일치하는지 확인(오래된 파일을 쓰는 사고 방지)
    pf = prof.set_index("page_id")
    assert set(pf.index) == set(pages.index), "page_profile의 면 목록이 다름"
    assert (pf.n.astype(int) == pages.n.reindex(pf.index)).all(), "page_profile의 n이 다시 계산한 값과 다름"
    for c in CATS:
        diff = (pf[f"pct_{c}"].astype(float) - 100 * pages[c].reindex(pf.index) / pages.n.reindex(pf.index)).abs().max()
        assert diff < 0.11, f"page_profile pct_{c}가 다시 계산한 값과 다름(최대 차 {diff:.2f})"
    sm = summ.set_index("period")
    for per, g in pages.groupby("period"):
        for c in CATS:
            assert abs(float(sm.loc[per, f"pct_{c}"]) - 100 * g[c].sum() / g.n.sum()) < 0.11, f"summary_period_category 불일치: {per} {c}"

    key = d.set_index("snippet_id")
    assert not inst.duplicated(["ngram", "snippet_id"]).any(), "ngram_instances에 중복 행"
    for col in ("page_id", "period", "category"):
        assert (inst[col].values == key.loc[inst.snippet_id, col].values).all(), f"ngram_instances의 {col}이 현재 데이터와 다름"
    return d, pages, prof, inst


def shares(pages):
    return pages[CATS].div(pages.n, axis=0)


def period_category(pages):
    sh = shares(pages)
    rows = []
    for per in sorted(pages.period.unique()):
        g = pages[pages.period == per]
        s = sh.loc[g.index]
        label = period_label(per, int(g.n.sum()))
        for c in CATS:
            pooled = g[c].sum() / g.n.sum()
            rows.append({
                "period": per, "period_label": label, "category": c, "n_snippets": int(g.n.sum()), "n_pages": len(g),
                "pooled_pct": pct(pooled), "page_mean_pct": pct(s[c].mean()), "page_median_pct": pct(s[c].median()),
                "page_sd_pct": pct(s[c].std(ddof=1)), "page_min_pct": pct(s[c].min()), "page_max_pct": pct(s[c].max()),
                "diff_pct": round(pct(s[c].mean()) - pct(pooled), 1),
            })
    return pd.DataFrame(rows)


def ngram_period(inst, a):
    periods = sorted(inst.period.unique())
    grams = sorted(inst.ngram.unique())
    rows = []
    for scope in ["ALL"] + periods:
        sub = inst if scope == "ALL" else inst[inst.period == scope]
        for g in grams:
            x = sub[sub.ngram == g]
            tf, df_ = len(x), x.page_id.nunique()
            top = x.page_id.value_counts().iloc[0] / tf if tf else None
            rows.append({
                "scope": scope, "ngram": g, "n_words": len(g.split()), "tf": tf, "df_pages": df_,
                "tf_per_df": round(tf / df_, 2) if df_ else None, "top_page_share": round(top, 3) if tf else None,
                "single_page_dominant": bool(tf >= a.min_tf and top >= a.dom_share) if tf else False,
            })
    t = pd.DataFrame(rows)
    out = []
    for _, g in t.groupby("scope", sort=False):
        g = g.copy()
        pos = g[g.tf > 0]
        for col, keys in (("rank_tf", ["tf", "df_pages", "ngram"]), ("rank_df", ["df_pages", "tf", "ngram"])):
            s = pos.sort_values(keys, ascending=[False, False, True])
            g[col] = pd.Series(range(1, len(s) + 1), index=s.index)
        g["rank_shift"] = g.rank_tf - g.rank_df  # 양수면 단순 빈도보다 출현 지면 수 기준에서 순위가 올라감
        out.append(g)
    return pd.concat(out).reset_index(drop=True)


def leave_out(pages, prof, a):
    pf = prof.copy()
    pf["n"] = pf.n.astype(int)
    for c in CATS:
        pf[f"pct_{c}"] = pf[f"pct_{c}"].astype(float)
    pf["max_share"] = pf[[f"pct_{c}" for c in CATS]].max(axis=1)
    vol = pf.sort_values(["n", "page_id"], ascending=[False, True])
    con = pf[pf.n >= a.min_n].sort_values(["max_share", "n", "page_id"], ascending=[False, False, True])
    orders = {"volume": vol, "concentration": con}
    sh = shares(pages)
    base = {}
    rows = []
    for crit, order in orders.items():
        for k in (0, 1, 3, 5):
            ex = order.head(k)
            keep = pages.drop(index=ex.page_id)
            detail = "; ".join(f"{r.page_id} ({r.place}, n={r.n}, 최대 범주 {r.max_share:.0f}%)" for r in ex.itertuples())
            for per in sorted(pages.period.unique()):
                g = keep[keep.period == per]
                row = {"criterion": crit, "k_excluded": k, "excluded_pages": detail, "period": per, "n_pages_left": len(g), "n_snippets_left": int(g.n.sum())}
                for c in CATS:
                    row[f"pooled_pct_{c}"] = pct(g[c].sum() / g.n.sum()) if len(g) else None
                for c in CATS:
                    row[f"page_mean_pct_{c}"] = pct(sh.loc[g.index, c].mean()) if len(g) else None
                if k == 0:
                    for c in CATS:
                        base[(per, c)] = (row[f"pooled_pct_{c}"], row[f"page_mean_pct_{c}"])
                for c in CATS:
                    row[f"delta_pooled_pp_{c}"] = round(row[f"pooled_pct_{c}"] - base[(per, c)][0], 1) if len(g) else None
                row["thin_period"] = len(g) <= 2
                rows.append(row)
    return pd.DataFrame(rows)


def entropy(p):
    return -sum(x * math.log2(x) for x in p if x > 0)


def page_diversity(pages, a):
    sh = shares(pages)
    rows = []
    for pid, r in pages.iterrows():
        s = sh.loc[pid]
        dom = s.idxmax()
        h = entropy(s.values)
        rows.append({
            "level": "page", "period": r.period, "page_id": pid, "date": r.date, "place": r.place, "n": int(r.n), "small_n": r.n < 10,
            "dominant_category": dom, "dominant_share_pct": pct(s[dom]), "entropy_bits": round(h, 3), "entropy_norm": round(h / math.log2(len(CATS)), 3),
            "page_type": "단일 범주 지면" if s[dom] >= a.single_th else ("우세 범주 지면" if s[dom] >= a.dominant_th else "혼재 지면"),
        })
    pg = pd.DataFrame(rows)
    per_rows = []
    for per in sorted(pages.period.unique()):
        g = pg[pg.period == per]
        ps = pages[pages.period == per]
        pooled = (ps[CATS].sum() / ps.n.sum()).values
        mean_h = g.entropy_norm.mean()
        pooled_h = entropy(pooled) / math.log2(len(CATS))
        per_rows.append({
            "level": "period", "period": per, "page_id": period_label(per, int(ps.n.sum())), "n": int(ps.n.sum()), "n_pages": len(g),
            "mean_entropy_norm": round(mean_h, 3), "median_entropy_norm": round(g.entropy_norm.median(), 3), "sd_entropy_norm": round(g.entropy_norm.std(ddof=1), 3),
            "n_single": int((g.page_type == "단일 범주 지면").sum()), "n_dominant": int((g.page_type == "우세 범주 지면").sum()), "n_mixed": int((g.page_type == "혼재 지면").sum()),
            "dominant_category_counts": "; ".join(f"{c} {n}" for c, n in g.dominant_category.value_counts().items()),
            "pooled_entropy_norm": round(pooled_h, 3), "between_page_gap": round(pooled_h - mean_h, 3),
        })
    return pd.concat([pg, pd.DataFrame(per_rows)], ignore_index=True)


def show(title, frame):
    print(f"\n[{title}]")
    print(frame.to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="CSV 4개를 저장(없으면 터미널 출력만)")
    ap.add_argument("--out-dir", type=Path, default=PROC, help="저장 폴더(기본 data/processed)")
    ap.add_argument("--min-tf", type=int, default=5, help="단일 면 집중 표시에 필요한 최소 TF")
    ap.add_argument("--dom-share", type=float, default=0.5, help="한 면이 차지하는 TF 비중이 이 값 이상이면 단일 면 집중")
    ap.add_argument("--min-n", type=int, default=10, help="집중도 기준 극단 면 선정에서 요구하는 최소 조각 수")
    ap.add_argument("--single-th", type=float, default=0.9, help="지배 범주 비중이 이 값 이상이면 단일 범주 지면")
    ap.add_argument("--dominant-th", type=float, default=0.6, help="이 값 이상이면 우세 범주 지면, 미만이면 혼재 지면")
    a = ap.parse_args()

    d, pages, prof, inst = load()
    print(f"무결성 통과: {len(d)}조각, {len(pages)}면(시기당 5면), page_profile·summary_period_category·ngram_instances와 재계산값 일치")

    t1 = period_category(pages)
    t2 = ngram_period(inst, a)
    t3 = leave_out(pages, prof, a)
    t4 = page_diversity(pages, a)
    tables = dict(zip(OUT_NAMES, [t1, t2, t3, t4]))

    w = t1.pivot(index="period_label", columns="category", values="diff_pct")[CATS].reset_index()
    show("1) 면 평균 − 합산 비율 (diff_pct, %p)", w)
    show("1) 면 평균 ± 표준편차 (%)", t1.assign(v=t1.page_mean_pct.astype(str) + " ± " + t1.page_sd_pct.astype(str)).pivot(index="period_label", columns="category", values="v")[CATS].reset_index())
    all_ = t2[t2.scope == "ALL"]
    show("2) 전체 기간 N-gram: TF·DF 순위 비교(상위 12, DF 순)", all_[all_.tf > 0].sort_values("rank_df").head(12)[["ngram", "tf", "df_pages", "tf_per_df", "top_page_share", "single_page_dominant", "rank_tf", "rank_df", "rank_shift"]])
    show("2) 단일 면에 몰린 표현(시기별)", t2[(t2.scope != "ALL") & t2.single_page_dominant][["scope", "ngram", "tf", "df_pages", "top_page_share"]])
    for crit in ("volume", "concentration"):
        x = t3[t3.criterion == crit]
        ex = x[x.k_excluded == 5].excluded_pages.iloc[0]
        print(f"\n3) {crit} 기준 상위 5개 제외 면: {ex}")
        piv = x.pivot(index="period", columns="k_excluded", values="pooled_pct_종교·기원")
        piv.columns = [f"제외 {c}" for c in piv.columns]
        show(f"3) {crit}: 종교·기원 합산 비율(%) 변화", piv.reset_index())
    show("4) 시기별 지면 다양성", t4[t4.level == "period"][["period", "n_pages", "mean_entropy_norm", "pooled_entropy_norm", "between_page_gap", "n_single", "n_dominant", "n_mixed", "dominant_category_counts"]])
    print("\n※ 시기당 5개 면 표본이라 면 단위 표준편차·중앙값은 매우 불안정함. v0.3 분류는 검증 표본 관찰 후 보정한 탐색적 결과이며 ngram_instances에는 상위 선정 n-gram 29개만 있음.")

    if not a.write:
        print("\n저장하지 않음(--write 없음)")
        return
    paths = [a.out_dir / n for n in OUT_NAMES]
    clash = [str(p) for p in paths if p.exists()]
    if clash:
        sys.exit("중단: 이미 존재하는 파일이 있어 덮어쓰지 않음\n  " + "\n  ".join(clash))
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(a.out_dir / name, index=False, encoding="utf-8-sig", mode="x")
    print(f"\n저장 완료: CSV {len(tables)}개({a.out_dir})")


if __name__ == "__main__":
    main()
