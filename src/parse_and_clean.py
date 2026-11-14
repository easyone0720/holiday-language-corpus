import argparse
import json
import re
import sys
from bisect import bisect_right
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process
from spellchecker import SpellChecker

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "saved" / "christmas"
OUT_PATH = ROOT / "data" / "processed" / "kwic_snippets.csv"

WINDOW = 30
NOISE_CHARS = "^»«|<>·•■*_\\~{}"
HIT_RE = re.compile(r"christ ?mas", re.I)  # 줄바꿈으로 갈라진 'Christ mas'도 히트로 잡되 글자는 고치지 않음
DUP_THRESHOLD = 85


def load_pairs(raw_dir):
    pages = {p.name[:-len("_page.json")]: p for p in raw_dir.glob("*/*_page.json")}
    texts = {p.name[:-len("_text.json")]: p for p in raw_dir.glob("*/*_text.json")}
    orphan = sorted(set(pages) ^ set(texts))
    docs = []
    for key in sorted(set(pages) & set(texts)):
        page = json.load(open(pages[key], encoding="utf-8"))
        text = json.load(open(texts[key], encoding="utf-8"))
        full_text = text[next(iter(text))]["full_text"]  # 최상위 키는 세그먼트 경로라 하드코딩 금지
        item = page["item"]
        docs.append(dict(
            page_id=key,
            date=item.get("date_issued"),
            newspaper_title=(item.get("newspaper_title") or [""])[0].strip(),
            place=item.get("place_of_publication"),
            page_no=page["pagination"]["current"],
            url=page["resource"]["url"].split("?")[0],  # 검색어 파라미터 제거
            full_text=full_text,
        ))
    return docs, orphan


def period_of(date):
    y = int(date[:4])
    return "1960–63" if y >= 1960 else f"{y // 10 * 10}s"


def period_label(period, n):
    return f"{period} (4 yrs, n={n})" if period == "1960–63" else f"{period} (n={n})"


def clean_with_map(raw, join_only_before_lower=True):
    """정제 텍스트와 정제 문자 -> 원문 인덱스 매핑(snippet_raw 복원용)."""
    cur = list(enumerate(raw))

    # 하이픈 결합이 반드시 가장 먼저. 뒤가 대문자면 이웃 단 글자일 수 있어 결합하지 않음
    out, i = [], 0
    while i < len(cur):
        if (cur[i][1] == "-" and i + 1 < len(cur) and cur[i + 1][1] == "\n"
                and (not join_only_before_lower
                     or (i + 2 < len(cur) and cur[i + 2][1].islower()))):
            i += 2
            continue
        out.append(cur[i])
        i += 1

    cur = [(ix, " " if c == "\n" else c) for ix, c in out]

    out = []
    for ix, c in cur:
        out += [(ix, " "), (ix, "—"), (ix, " ")] if c == "—" else [(ix, c)]

    cur = [(ix, c) for ix, c in out if c not in NOISE_CHARS]

    out = []
    for ix, c in cur:
        if c.isspace():
            if out and out[-1][1] != " ":
                out.append((ix, " "))
        else:
            out.append((ix, c))
    while out and out[-1][1] == " ":
        out.pop()
    return "".join(c for _, c in out), [ix for ix, _ in out]


def find_hits(clean, toks):
    starts = [s for s, _ in toks]
    hits, seen = [], set()
    for m in HIT_RE.finditer(clean):
        ti = bisect_right(starts, m.start()) - 1
        if ti >= 0 and ti not in seen:
            seen.add(ti)
            hits.append((ti, m.group(0)))
    return hits


def select_hits(hits, policy):
    # strict: 앞뒤 30단어 창이 서로 겹치지 않도록 61단어 이상 떨어진 히트만 채택
    gap = {"all": 0, "greedy": WINDOW + 1, "strict": 2 * WINDOW + 1}[policy]
    kept, last = [], None
    for h in hits:
        if last is None or h[0] - last >= gap:
            kept.append(h)
            last = h[0]
    return kept


_SP = SpellChecker()


def dict_ratio(text):
    words = [w.lower() for w in re.findall(r"[A-Za-z]+", text) if len(w) >= 2]
    if not words:
        return None
    return round(sum(w in _SP for w in words) / len(words), 3)


def build_snippets(doc, policy, join_only_before_lower):
    raw = doc["full_text"]
    clean, imap = clean_with_map(raw, join_only_before_lower)
    # 단어 수는 영숫자가 있는 토큰만 센다(대시·기호 단독 토큰 제외)
    toks = [(m.start(), m.end()) for m in re.finditer(r"\S+", clean) if re.search(r"\w", m.group())]
    all_hits = find_hits(clean, toks)
    out = []
    for ti, matched in select_hits(all_hits, policy):
        lo, hi = max(0, ti - WINDOW), min(len(toks) - 1, ti + WINDOW)
        cs, ce = toks[lo][0], toks[hi][1]
        out.append(dict(
            hit_text=matched,
            is_split_hit=" " in matched,
            n_hits_in_window=sum(lo <= t <= hi for t, _ in all_hits),
            snippet_raw=raw[imap[cs]: imap[ce - 1] + 1],
            snippet_clean=clean[cs:ce],
        ))
    return out, len(all_hits)


def mark_duplicates(df):
    texts = df["snippet_clean"].str.lower().tolist()
    M = process.cdist(texts, texts, scorer=fuzz.ratio, score_cutoff=DUP_THRESHOLD,
                      workers=-1, dtype=np.uint8)
    df["is_duplicate"], df["dup_of"] = False, ""
    for i in range(len(df)):
        for j in range(i):
            # 같은 면 안의 반복 문구는 복제 기사가 아니므로 다른 면끼리만 비교
            if M[i, j] and df.at[j, "page_id"] != df.at[i, "page_id"] and not df.at[j, "is_duplicate"]:
                df.at[i, "is_duplicate"], df.at[i, "dup_of"] = True, df.at[j, "snippet_id"]
                break
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", choices=["all", "greedy", "strict"], default="strict")
    ap.add_argument("--join-all", action="store_true", help="-\\n 뒤가 대문자여도 결합")
    ap.add_argument("--write", action="store_true", help="없으면 화면 출력만")
    a = ap.parse_args()

    if a.write and OUT_PATH.exists():
        sys.exit(f"중단: {OUT_PATH} 이미 존재(덮어쓰기 금지)")

    docs, orphan = load_pairs(RAW_DIR)
    if orphan:
        sys.exit(f"짝이 없는 파일: {orphan}")
    print(f"쌍 {len(docs)}개")

    rows, n_hits = [], 0
    for d in docs:
        snips, n_all = build_snippets(d, a.policy, not a.join_all)
        n_hits += n_all
        for k, s in enumerate(snips):
            rows.append({**{c: d[c] for c in ("page_id", "date", "newspaper_title", "place", "page_no", "url")},
                         "period": period_of(d["date"]), "hit_no": k + 1, **s})
    df = pd.DataFrame(rows).sort_values(["date", "page_id", "hit_no"]).reset_index(drop=True)
    df["dict_ratio"] = df["snippet_clean"].map(dict_ratio)
    df.insert(0, "snippet_id", [f"S{i + 1:04d}" for i in range(len(df))])
    df = mark_duplicates(df)

    print(f"[{a.policy}] 전체 히트 {n_hits} -> 조각 {len(df)}, 중복 {int(df.is_duplicate.sum())}, "
          f"분리 히트 {int(df.is_split_hit.sum())}, dict_ratio<0.8 {int((df.dict_ratio < 0.8).sum())}")
    for p, n in df.groupby("period").size().items():
        print("  ", period_label(p, n))

    if a.write:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
        print("저장:", OUT_PATH)


if __name__ == "__main__":
    main()
