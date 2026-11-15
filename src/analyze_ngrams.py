import argparse
import re
import sys
from collections import Counter

import pandas as pd

from extract_discourse_samples import CATS, PROC, STOP, VER, load, pct

SUBS = ["예배·신학", "기원·역사해설", "일상·사교형", "자선·나눔형", "판촉·광고형", "상업화 비판·성찰형", "시사·단신"]
TARGETS = ["merry christmas", "christmas tree", "christmas eve", "christmas dinner", "christmas gifts", "christmas seals"]
HIT_RE = re.compile(r"christ ?mas", re.I)
# 단어 토큰과 구 경계 토큰(. , ! ? ; : —). 경계를 넘는 n-gram은 만들지 않는다
TOKEN_RE = re.compile(r"[a-z]+(?:'[a-z]+)?|[.,!?;:—]")
CENTER_IDX = 30  # KWIC 창은 중심어 앞 30단어이므로 왼쪽이 꽉 찬 조각은 중심어가 정확히 30번째에 있다
MIN_LEN = 3


def center_span(text):
    # 한 조각 안의 여러 Christmas 중 이 조각의 중심 히트를 고른다. 면 시작이라 왼쪽이 짧은 조각은 첫 히트가 중심
    hits = []
    for m in HIT_RE.finditer(text):
        left = len([t for t in text[: m.start()].split() if re.search(r"\w", t)])
        hits.append((left, m))
    for left, m in hits:
        if left == CENTER_IDX:
            return m, "idx30"
    return hits[0][1], "first"


def center_ngrams(text):
    low = text.lower()
    m, rule = center_span(text)
    toks = [(t[:-2] if t.endswith("'s") else t, s, e) for t, s, e in ((x.group(), x.start(), x.end()) for x in TOKEN_RE.finditer(low))]
    c = next((i for i, (_, s, e) in enumerate(toks) if s <= m.start() < e), None)
    if c is None:
        return [], rule, "no_token"
    # 분리 표기(Christ mas)는 두 토큰을 하나의 중심어로 취급
    if toks[c][0] == "christ" and c + 1 < len(toks) and toks[c + 1][0] == "mas":
        words = [t for t, _, _ in toks[:c]] + ["christmas"] + [t for t, _, _ in toks[c + 2:]]
        ci = c
        kind = "split"
    else:
        words = [t for t, _, _ in toks]
        ci = c
        kind = "exact" if toks[c][0] == "christmas" else "variant"
    if kind == "variant":  # christmases, christmastide 등은 n-gram에서 제외
        return [], rule, kind

    def ok(w):  # 이웃 단어는 구 경계가 아닌 내용어
        return w.isalpha() and len(w) >= MIN_LEN and w not in STOP

    L = [words[ci - i] if ci - i >= 0 else None for i in (1, 2)]
    R = [words[ci + i] if ci + i < len(words) else None for i in (1, 2)]
    out = []
    if L[0] and ok(L[0]):
        out.append(f"{L[0]} christmas")
        if L[1] and ok(L[1]):
            out.append(f"{L[1]} {L[0]} christmas")
    if R[0] and ok(R[0]):
        out.append(f"christmas {R[0]}")
        if R[1] and ok(R[1]):
            out.append(f"christmas {R[0]} {R[1]}")
        if L[0] and ok(L[0]):
            out.append(f"{L[0]} christmas {R[0]}")
    return out, rule, kind


def build(d):
    rows, diag = [], Counter()
    for r in d.itertuples():
        grams, rule, kind = center_ngrams(r.snippet_clean)
        diag[rule] += 1
        diag[kind] += 1
        for g in set(grams):
            rows.append({"snippet_id": r.snippet_id, "ngram": g, "n_words": len(g.split())})
    return pd.DataFrame(rows), diag


def frequency(inst, n, a):
    t = inst.groupby(["ngram", "n_words"]).size().rename("n_snippets").reset_index()
    t["pct_snippets"] = t.n_snippets.map(lambda x: pct(x, n))
    top = pd.concat([
        t[t.n_words == 2].sort_values(["n_snippets", "ngram"], ascending=[False, True]).head(a.top_bi),
        t[t.n_words == 3].sort_values(["n_snippets", "ngram"], ascending=[False, True]).head(a.top_tri),
    ])
    top = top[top.n_snippets >= a.min_count]
    pinned = pd.DataFrame({"ngram": TARGETS, "n_words": 2}).merge(t[["ngram", "n_snippets", "pct_snippets"]], on="ngram", how="left").fillna({"n_snippets": 0, "pct_snippets": 0})
    out = pd.concat([top, pinned]).drop_duplicates("ngram")
    out["pinned"] = out.ngram.isin(TARGETS)
    out["n_snippets"] = out.n_snippets.astype(int)
    return out.sort_values(["n_words", "n_snippets", "ngram"], ascending=[True, False, True]).reset_index(drop=True)


def period_table(inst, d, sel):
    rows = []
    for p in sorted(d.period.unique()):
        ids = set(d[d.period == p].snippet_id)
        n = len(ids)
        label = f"{p} (4 yrs, n={n})" if p == "1960–63" else f"{p} (n={n})"
        sub = inst[inst.snippet_id.isin(ids)]
        vc = sub.ngram.value_counts()
        for g in sel:
            rows.append({"ngram": g, "period": p, "period_label": label, "n_period": n, "n_snippets": int(vc.get(g, 0)), "pct_snippets": pct(vc.get(g, 0), n)})
    return pd.DataFrame(rows)


def cross_table(inst, d, sel, col, order):
    m = inst[inst.ngram.isin(sel)].merge(d[["snippet_id", col]], on="snippet_id")
    ct = pd.crosstab(m.ngram, m[col]).reindex(index=sel, columns=order, fill_value=0)
    out = pd.DataFrame({"ngram": sel, "n_total": ct.sum(axis=1).values})
    for c in order:
        out[f"n_{c}"] = ct[c].values
    for c in order:
        out[f"pct_{c}"] = [pct(x, t) if t else None for x, t in zip(ct[c].values, out.n_total)]
    out["small_n"] = out.n_total < 10  # 10건 미만은 비율이 불안정
    base = {"ngram": "(전체 조각)", "n_total": len(d), "small_n": False}
    vc = d[col].value_counts()
    base.update({f"n_{c}": int(vc.get(c, 0)) for c in order})
    base.update({f"pct_{c}": pct(vc.get(c, 0), len(d)) for c in order})
    return pd.concat([out, pd.DataFrame([base])], ignore_index=True)


def show(title, frame):
    print(f"\n[{title}]")
    print(frame.to_string(index=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--top-bi", type=int, default=30)
    ap.add_argument("--top-tri", type=int, default=20)
    ap.add_argument("--min-count", type=int, default=5, help="상위 목록에 넣을 최소 조각 수(지정 표현 6개는 항상 포함)")
    a = ap.parse_args()

    d = load()
    print(f"무결성 통과: {len(d)}행, 전부 ok, 프롬프트 v0.3-presenter-rule")
    inst, diag = build(d)
    print(f"중심 히트 판정: idx30 {diag['idx30']}건, 첫 히트(면 시작) {diag['first']}건 | 형태: 정확 {diag['exact']}, 분리 표기 {diag['split']}, 변형(제외) {diag['variant']}, 토큰 없음 {diag['no_token']}")

    freq = frequency(inst, len(d), a)
    sel = freq.ngram.tolist()
    inst = inst[inst.ngram.isin(sel)]
    traced = inst.merge(d[["snippet_id", "period", "page_id", "category", "sub_type", "confidence"]], on="snippet_id").sort_values(["ngram", "snippet_id"])
    tables = {
        "ngram_frequency": freq,
        "ngram_period": period_table(inst, d, sel),
        "ngram_category": cross_table(inst, d, sel, "category", CATS),
        "ngram_subtype": cross_table(inst, d, sel, "sub_type", SUBS),
        "ngram_instances": traced[["ngram", "snippet_id", "period", "page_id", "category", "sub_type", "confidence"]],
    }

    show("n-gram 빈도 (중심 Christmas 기준, 조각 수)", freq)
    pt = tables["ngram_period"].pivot(index="ngram", columns="period", values="pct_snippets").loc[TARGETS]
    show("지정 표현의 시기별 포함 비율(%)", pt.reset_index())
    show("n-gram × 4대 범주 (행 %)", tables["ngram_category"][["ngram", "n_total"] + [f"pct_{c}" for c in CATS] + ["small_n"]])
    print("\n※ v0.3 분류는 검증 표본 관찰 후 보정한 탐색적 결과. LLM은 중심어 주변 문맥 전체를 보고 판정하므로 n-gram과 범주의 대응은 독립된 증거가 아니라 일관성 점검으로 해석.")

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
