import argparse
import csv
import os
import sys
import time
from pathlib import Path

import anthropic
import pandas as pd

MODEL = os.environ.get("CLASSIFY_MODEL", "claude-sonnet-5-5")
PROMPT_VERSION = "v0.1-draft"

TAXONOMY = {
    "종교·기원": ["예배·신학", "기원·역사해설"],
    "가정·사교·공동체": ["일상·사교형", "자선·나눔형"],
    "상업·소비": ["판촉·광고형", "상업화 비판·성찰형"],
    "시사·기타": ["시사·단신"],
}
VALID_PAIRS = {(c, s) for c, subs in TAXONOMY.items() for s in subs}

SYSTEM_PROMPT = """You code short excerpts (~60 words) from OCR-scanned US newspapers (1900-1963), each centred on the word "Christmas".
Assign exactly ONE category and ONE sub_type describing HOW Christmas is being talked about in the context around the keyword.
Judge only from the excerpt text. The text contains OCR noise: do not try to reconstruct garbled words, and do not guess the date or newspaper.
If the excerpt mixes topics, choose the one closest to the keyword "Christmas".

CATEGORIES AND SUB_TYPES (use these exact labels)
1. 종교·기원
   - 예배·신학: church services, sermons, worship or carol services, Christ-centred or biblical message, religiously framed blessings.
   - 기원·역사해설: explanation of the origin or history of Christmas (the Dec 25 date, Roman/Jewish/pagan antecedents, history of customs).
2. 가정·사교·공동체
   - 일상·사교형: family meals and gatherings, visits, parties, balls, club or school entertainments and programs, Santa visits, personal social news ("spent Christmas with relatives").
   - 자선·나눔형: charity and giving to others: Salvation Army kettles, relief funds, baskets for the poor, toy drives, fundraising for the needy.
3. 상업·소비
   - 판촉·광고형: store ads, sales, gift-buying promotions, merchants' seasonal greetings or thank-you ads, shopping schedules.
   - 상업화 비판·성찰형: commentary that criticises commercialism or materialism, or stresses love and giving over buying.
4. 시사·기타
   - 시사·단신: war, politics, public affairs, crime/accident news, weather, notices, schedules, closings, or anything fitting none of the above, including "Christmas" used only as a date marker.

TIE-BREAK RULES
- An advertisement or purchase appeal is 상업·소비/판촉·광고형 even if its wording is warm or religious.
- Fundraising for the needy is 자선·나눔형 even when a church runs it; the church service or program itself is 예배·신학.
- School/community Christmas programs (recitations, songs, pageants) are 일상·사교형 unless the focus is worship or doctrine.
- "Before/after Christmas" used only as a date marker in news or notices is 시사·단신.
- If the text is badly garbled, decide from the readable parts and set confidence to "low".
Answer only by calling the record_label tool."""

TOOL = {
    "name": "record_label",
    "description": "Record the classification of one excerpt.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": list(TAXONOMY)},
            "sub_type": {"type": "string", "enum": [s for v in TAXONOMY.values() for s in v]},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "rationale": {"type": "string", "description": "근거를 한국어 40자 이내로"},
        },
        "required": ["category", "sub_type", "confidence", "rationale"],
    },
}

COLS = ["snippet_id", "category", "sub_type", "confidence", "rationale", "status", "model", "prompt_version"]


def classify(client, text):
    err = None
    for attempt in range(3):
        try:
            r = client.messages.create(
                model=MODEL, max_tokens=300, temperature=0,  # 모델이 temperature를 받지 않으면 제거
                system=SYSTEM_PROMPT, tools=[TOOL],
                tool_choice={"type": "tool", "name": "record_label"},
                messages=[{"role": "user", "content": f"<excerpt>\n{text}\n</excerpt>"}],
            )
            return next(b for b in r.content if b.type == "tool_use").input
        except Exception as e:
            err = e
            time.sleep(2 ** attempt)
    return {"error": str(err)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()

    out_path = Path(a.out)
    if out_path.exists():
        sys.exit(f"중단: {out_path} 이미 존재. 프롬프트를 고쳤다면 PROMPT_VERSION과 파일명을 새로 지정")
    if "ANTHROPIC_API_KEY" not in os.environ:
        sys.exit("ANTHROPIC_API_KEY가 필요합니다")

    df = pd.read_csv(a.input)
    if "is_duplicate" in df:
        df = df[~df.is_duplicate]
    if a.limit:
        df = df.head(a.limit)

    # 프롬프트 튜닝은 sample_design_20만 사용. sample_validation_45로 튜닝하면 일치율이 부풀려짐
    # 연도·신문명은 보내지 않아 가설 방향으로 쏠리는 것을 막음
    client = anthropic.Anthropic()
    with open(out_path, "x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for _, r in df.iterrows():
            out = classify(client, r["snippet_clean"])
            ok = "error" not in out and (out.get("category"), out.get("sub_type")) in VALID_PAIRS
            w.writerow({
                "snippet_id": r["snippet_id"],
                **{k: out.get(k, "") for k in COLS[1:5]},
                "status": "ok" if ok else f"CHECK:{out.get('error', '범주/세부 조합 오류')}",
                "model": MODEL,
                "prompt_version": PROMPT_VERSION,
            })
            f.flush()


if __name__ == "__main__":
    main()
