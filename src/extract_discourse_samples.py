import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
VER = "v0.3"
PROMPT = "v0.3-presenter-rule"
EXPECTED_N = 788
SEED = 20261115

CATS = ["종교·기원", "가정·사교·공동체", "상업·소비", "시사·기타"]
CONFS = ["high", "medium", "low"]

# 공기어 집계에서 뺄 불용어. 의미가 있는 고어(thee, thy 등)와 호칭(mr, mrs)은 일부러 남긴다
STOP = set("""a about above after again against all am an and any are as at be because been before being below between both
but by can could did do does doing down during each few for from further had has have having he her here hers herself him
himself his how i if in into is it its itself just me more most my myself no nor not now of off on once only or other our
ours ourselves out over own same she should so some such than that the their theirs them themselves then there these they
this those through to too under until up very was we were what when where which while who whom why will with would you your
yours yourself yourselves said also one two may shall upon per get got let ing""".split())  # ing는 줄바꿈 OCR 잔여 조각
EXCLUDE_HIT = {"christmas", "xmas"}
TOKEN_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")
MIN_LEN = 3


def pct(n, d):
    return round(100 * n / d, 1)


def load():
    k = pd.read_csv(PROC / "kwic_snippets.csv", encoding="utf-8-sig")
    p = pd.read_csv(PROC / f"pred_full_{VER}.csv", encoding="utf-8-sig", keep_default_na=False)
    assert len(k) == EXPECTED_N and len(p) == EXPECTED_N, f"행 수 불일치: kwic {len(k)}, pred {len(p)}"
    df = k.merge(p, on="snippet_id", how="outer", validate="1:1", indicator=True)
    assert (df["_merge"] == "both").all(), "병합 시 한쪽에만 있는 snippet_id 존재"
    assert (df.status == "ok").all(), "ok 아닌 행 존재"
    assert set(df.prompt_version) == {PROMPT}, f"프롬프트 버전 혼재: {set(df.prompt_version)}"
    assert df.confidence.isin(CONFS).all() and df.category.isin(CATS).all()
    return df.drop(columns="_merge")


def collocates(text, span):
    # 검색어(분리 표기 Christ mas 포함) 앞뒤 span 단어. 검색어 자체와 불용어는 제외
    toks = TOKEN_RE.findall(text.lower())
    hits = set()
    for i, t in enumerate(toks):
        if t in EXCLUDE_HIT:
            hits.add(i)
        elif t == "christ" and i + 1 < len(toks) and toks[i + 1] == "mas":
            hits.update((i, i + 1))
    near = set()
    for i in hits:
        near.update(range(max(0, i - span), min(len(toks), i + span + 1)))
    out = []
    for i in sorted(near - hits):
        t = toks[i][:-2] if toks[i].endswith("'s") else toks[i]
        if "'" not in t and len(t) >= MIN_LEN and t not in STOP:
            out.append(t)
    return out


def doc_freq(token_lists):
    c = Counter()
    for toks in token_lists:
        c.update(set(toks))
    return c


def top_words(token_lists, corpus_df, n_corpus, top_n, min_lift_df):
    # 빈도 순위와 변별 순위(그룹 비중 ÷ 전체 비중)를 함께 낸다. 검정 없이 기술 비교만
    n = len(token_lists)
    n_tok = Counter(t for toks in token_lists for t in toks)
    df_ = doc_freq(token_lists)
    rows = [{"word": w, "n_tokens": n_tok[w], "n_snippets": df_[w], "pct_snippets": pct(df_[w], n),
             "lift": round((df_[w] / n) / (corpus_df[w] / n_corpus), 2)} for w in df_]
    t = pd.DataFrame(rows)
    freq = t.sort_values(["n_snippets", "n_tokens", "word"], ascending=[False, False, True]).head(top_n).assign(ranking="frequency")
    dist = t[t.n_snippets >= min_lift_df].sort_values(["lift", "n_snippets", "word"], ascending=[False, False, True]).head(top_n).assign(ranking="distinctive")
    return pd.concat([freq, dist], ignore_index=True)


def collocate_tables(d, a):
    d = d.assign(toks=d.snippet_clean.map(lambda s: collocates(s, a.span)))
    corpus_df, n_corpus = doc_freq(d.toks), len(d)
    by_cat, by_cell = [], []
    for c in CATS:
        g = d[d.category == c]
        by_cat.append(top_words(g.toks.tolist(), corpus_df, n_corpus, a.top_n, a.min_lift_df).assign(category=c, n_group=len(g)))
    for c in CATS:
        for p in sorted(d.period.unique()):
            g = d[(d.category == c) & (d.period == p)]
            if len(g) >= a.min_cell:  # 표본이 너무 작은 칸은 어휘 순위가 불안정해 제외
                by_cell.append(top_words(g.toks.tolist(), corpus_df, n_corpus, a.cell_top_n, a.min_lift_df).assign(category=c, period=p, n_group=len(g)))
    cols = ["category", "n_group", "ranking", "word", "n_tokens", "n_snippets", "pct_snippets", "lift"]
    return (pd.concat(by_cat, ignore_index=True)[cols],
            pd.concat(by_cell, ignore_index=True)[["category", "period"] + cols[1:]])


SRC_COLS = ["snippet_id", "date", "newspaper_title", "place", "page_no", "url"]
TXT_COLS = ["sub_type", "confidence", "rationale", "dict_ratio", "snippet_clean", "snippet_raw"]


def representative(d, k):
    # 고정 시드 무작위 추출. 대표성 보장이 아니라 정독 출발점용이다.
    # high가 k건 미만인 칸은 부족분만 medium으로 보충하고(confidence 열로 구분), 후보가 없으면 빈 행으로 남긴다
    rows = []
    for c in CATS:
        for p in sorted(d.period.unique()):
            cell = d[(d.category == c) & (d.period == p)]
            high, med = cell[cell.confidence == "high"], cell[cell.confidence == "medium"]
            base = {"category": c, "period": p, "n_cell": len(cell), "n_high_pool": len(high), "n_medium_pool": len(med)}
            pick = high.sample(min(k, len(high)), random_state=SEED)
            if len(pick) < k and len(med):
                pick = pd.concat([pick, med.sample(min(k - len(pick), len(med)), random_state=SEED)])
            if pick.empty:
                rows.append(base)
                continue
            for _, r in pick.sort_values(["confidence", "date"]).iterrows():  # high가 먼저 오도록 정렬
                rows.append({**base, **r[SRC_COLS + TXT_COLS].to_dict()})
    return pd.DataFrame(rows)


def low_tables(d):
    low = d[d.confidence == "low"].sort_values(["period", "page_id", "snippet_id"])
    rows = []
    for p in sorted(d.period.unique()):
        g = d[d.period == p]
        lo = g[g.confidence == "low"]
        rows.append({
            "period": p, "n": len(g), "n_low": len(lo), "pct_low": pct(len(lo), len(g)),
            **{f"low_{c}": int((lo.category == c).sum()) for c in CATS},
            "dict_ratio_mean_all": round(g.dict_ratio.mean(), 3),
            "dict_ratio_mean_low": round(lo.dict_ratio.mean(), 3) if len(lo) else None,
        })
    return low[["period", "category"] + SRC_COLS + TXT_COLS], pd.DataFrame(rows)


def page_profile(d, a):
    overall = {c: 100 * (d.category == c).mean() for c in CATS}
    rows = []
    for pid, g in d.groupby("page_id"):
        n = len(g)
        share = {c: 100 * (g.category == c).mean() for c in CATS}
        flags = [(c, share[c], share[c] - overall[c]) for c in CATS if n >= a.min_page_n and share[c] - overall[c] >= a.flag_pp]
        rows.append({
            "page_id": pid, "period": g.period.iloc[0], "date": g.date.iloc[0], "newspaper_title": g.newspaper_title.iloc[0],
            "place": g.place.iloc[0], "page_no": g.page_no.iloc[0], "url": g.url.iloc[0], "n": n,
            "n_low": int((g.confidence == "low").sum()), "pct_low": pct((g.confidence == "low").sum(), n),
            "dict_ratio_mean": round(g.dict_ratio.mean(), 3),
            **{f"pct_{c}": round(share[c], 1) for c in CATS},
            "top_category": max(CATS, key=share.get),
            "flag": "; ".join(f"{c} {s:.0f}% (전체 대비 +{x:.0f}pp)" for c, s, x in flags),
            "flag_snippet_ids": "; ".join(f"{c}: " + ",".join(g[g.category == c].snippet_id.head(10)) for c, _, _ in flags),
        })
    return pd.DataFrame(rows).sort_values(["period", "date"])


def show(title, frame, width=None):
    print(f"\n[{title}]")
    f = frame.copy()
    if width:
        for c in f.select_dtypes("object"):
            f[c] = f[c].astype(str).str.slice(0, width)
    print(f.to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="표를 파일로 저장(없으면 터미널 출력만)")
    ap.add_argument("--span", type=int, default=10, help="검색어 앞뒤 공기어 범위(단어 수)")
    ap.add_argument("--top-n", type=int, default=30)
    ap.add_argument("--cell-top-n", type=int, default=15)
    ap.add_argument("--min-cell", type=int, default=15, help="범주×시기 공기어를 내는 최소 조각 수")
    ap.add_argument("--min-lift-df", type=int, default=5, help="변별 순위에 넣을 최소 포함 조각 수")
    ap.add_argument("--k", type=int, default=2, help="범주×시기 칸당 대표 용례 수(high 부족분은 medium으로 보충)")
    ap.add_argument("--min-page-n", type=int, default=8)
    ap.add_argument("--flag-pp", type=float, default=30, help="면의 범주 비중이 전체보다 이 값(pp) 이상 높으면 표시")
    a = ap.parse_args()

    d = load()
    print(f"무결성 통과: {len(d)}행, 전부 ok, 프롬프트 {PROMPT}")

    by_cat, by_cell = collocate_tables(d, a)
    low, low_sum = low_tables(d)
    prof = page_profile(d, a)
    tables = {
        "discourse_collocates_category": by_cat,
        "discourse_collocates_category_period": by_cell,
        "discourse_representative": representative(d, a.k),
        "discourse_low_confidence": low,
        "discourse_low_summary": low_sum,
        "discourse_page_profile": prof,
    }

    for c in CATS:
        g = by_cat[by_cat.category == c]
        for r in ("frequency", "distinctive"):
            w = g[g.ranking == r].head(12)
            print(f"\n[{c} 공기어 {r}, n={g.n_group.iloc[0]}] " + ", ".join(f"{x.word}({x.n_snippets})" for x in w.itertuples()))
    print(f"\n범주×시기 공기어 칸 {by_cell[['category', 'period']].drop_duplicates().shape[0]}개 (조각 {a.min_cell}건 이상만)")
    rep = tables["discourse_representative"]
    cells = rep.groupby(["category", "period"], sort=False).agg(
        n_cell=("n_cell", "first"), n_high_pool=("n_high_pool", "first"), n_medium_pool=("n_medium_pool", "first"),
        picked_high=("confidence", lambda s: int((s == "high").sum())), picked_medium=("confidence", lambda s: int((s == "medium").sum())),
    ).reset_index()
    show("대표 용례 칸별 후보·선정 수", cells)
    show("low 신뢰도 요약", low_sum)
    show("특정 범주 비중이 높은 면", prof[prof.flag != ""][["page_id", "place", "page_no", "n", "flag"]])
    print("\n※ 대표 용례는 고정 시드 무작위 추출이며 대표성을 보장하지 않음. 시기당 5개 면 표본이라 면 특성이 어휘에 크게 반영됨.")

    if not a.write:
        print("\n저장하지 않음(--write 없음)")
        return
    paths = {n: PROC / f"{n}_{VER}.csv" for n in tables}
    clash = [str(p) for p in paths.values() if p.exists()]
    if clash:
        sys.exit("중단: 이미 존재하는 파일이 있어 덮어쓰지 않음\n  " + "\n  ".join(clash))
    for n, frame in tables.items():
        frame.to_csv(paths[n], index=False, encoding="utf-8-sig", mode="x")
    print(f"\n저장 완료: CSV {len(tables)}개({PROC})")


if __name__ == "__main__":
    main()
