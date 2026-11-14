import argparse
import csv
import os
import sys
import time
from pathlib import Path

import anthropic
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODEL = os.environ.get("CLASSIFY_MODEL", "claude-sonnet-5-5")

TAXONOMY = {
    "종교·기원": ["예배·신학", "기원·역사해설"],
    "가정·사교·공동체": ["일상·사교형", "자선·나눔형"],
    "상업·소비": ["판촉·광고형", "상업화 비판·성찰형"],
    "시사·기타": ["시사·단신"],
}
VALID_PAIRS = {(c, s) for c, subs in TAXONOMY.items() for s in subs}

HEAD_V1 = """You code short excerpts (~60 words) from OCR-scanned US newspapers (1900-1963), each centred on the word "Christmas".
Assign exactly ONE category and ONE sub_type describing HOW Christmas is being talked about in the context around the keyword.
Judge only from the excerpt text. The text contains OCR noise: do not try to reconstruct garbled words, and do not guess the date or newspaper.
If the excerpt mixes topics, choose the one closest to the keyword "Christmas".
"""

HEAD_V2 = """You code short excerpts (~60 words) from OCR-scanned US newspapers (1900-1963), each centred on the word "Christmas".
Assign exactly ONE category and ONE sub_type describing HOW Christmas is being talked about in the context around the keyword.
Judge only from the excerpt text, and do not guess the date or newspaper.
The text contains OCR noise. Read through it: when a word is clearly a misread of a common word (for example "tbe" for "the"), interpret it as the intended word. Never output corrections, and do not guess at words the context does not make clear.
If the excerpt mixes topics, choose the one closest to the keyword "Christmas".
"""

DEFINITIONS = """
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
"""

EDGE_RULES_V2 = """
EDGE-CASE RULES
1. Holiday greeting ads. A message that carries a named business or its proprietor and wishes customers or townspeople "Merry Christmas" or "Happy New Year", or thanks them for their patronage, is an advertisement even when it names no goods, prices or discounts. Always 상업·소비/판촉·광고형.
2. Community scenes. Naming a church or a Catholic hospital does not make an excerpt religious. When the focus is residents attending an event, a social note, a nurses' tree party, a town parade, a local club, or a school choir going caroling, classify it 가정·사교·공동체/일상·사교형. Use 종교·기원 only when the content is the service, sermon or Mass liturgy itself.
3. Worship versus origins. 예배·신학 covers Christmas service programs, Mass settings, offertory anthems, Christmas hymns, and devout or lyrical poems and songs that praise the birth of Jesus. 기원·역사해설 covers only writing that explains the historical or folkloric origin of customs such as the tree, Santa Claus or the date of December 25.
"""

TIE_BREAKS = """- An advertisement or purchase appeal is 상업·소비/판촉·광고형 even if its wording is warm or religious.
- Fundraising for the needy is 자선·나눔형 even when a church runs it; the church service or program itself is 예배·신학.
- School/community Christmas programs (recitations, songs, pageants) are 일상·사교형 unless the focus is worship or doctrine.
- "Before/after Christmas" used only as a date marker in news or notices is 시사·단신.
- If the text is badly garbled, decide from the readable parts and set confidence to "low".
Answer only by calling the record_label tool."""

# v0.1은 기준선이라 문구를 바꾸지 않는다. 고치면 새 버전 이름으로 추가할 것
PROMPTS = {
    "v0.1-draft": HEAD_V1 + DEFINITIONS + "\nTIE-BREAK RULES\n" + TIE_BREAKS,
    "v0.2-edge-rules": HEAD_V2 + DEFINITIONS + EDGE_RULES_V2 + "\nOTHER TIE-BREAKS\n" + TIE_BREAKS,
}

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


def classify(client, system, text):
    err = None
    for attempt in range(3):
        try:
            r = client.messages.create(
                model=MODEL, max_tokens=300, temperature=0,  # 모델이 temperature를 받지 않으면 제거
                system=system, tools=[TOOL],
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
    ap.add_argument("--prompt-version", required=True, choices=list(PROMPTS))
    ap.add_argument("--input", default=str(ROOT / "data/processed/sample_validation_45.csv"))
    ap.add_argument("--output", "--out", help="기본값: data/processed/pred_validation_<v0.1|v0.2>.csv")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true", help="API 호출 없이 입력 건수와 출력 경로만 확인")
    a = ap.parse_args()

    ver = a.prompt_version
    out_path = Path(a.output) if a.output else ROOT / "data" / "processed" / f"pred_validation_{ver.split('-')[0]}.csv"
    if out_path.exists():
        sys.exit(f"중단: {out_path} 이미 존재(덮어쓰기 금지). 다시 돌리려면 --output을 새로 지정")

    df = pd.read_csv(a.input, encoding="utf-8-sig")
    if "is_duplicate" in df:
        df = df[~df.is_duplicate]
    if a.limit:
        df = df.head(a.limit)

    if a.dry_run:
        print(f"입력 {len(df)}건 | 출력 {out_path} | 프롬프트 {ver} | 모델 {MODEL}")
        return
    if "ANTHROPIC_API_KEY" not in os.environ:
        sys.exit("ANTHROPIC_API_KEY가 필요합니다")

    # 프롬프트 튜닝은 sample_design_20만 사용. 검증 표본을 보고 고친 버전은 결과에 그 사실을 밝힐 것
    # 연도·신문명은 보내지 않아 가설 방향으로 쏠리는 것을 막음
    client = anthropic.Anthropic()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for _, r in df.iterrows():
            out = classify(client, PROMPTS[ver], r["snippet_clean"])
            ok = "error" not in out and (out.get("category"), out.get("sub_type")) in VALID_PAIRS
            w.writerow({
                "snippet_id": r["snippet_id"],
                **{k: out.get(k, "") for k in COLS[1:5]},
                "status": "ok" if ok else f"CHECK:{out.get('error', '범주/세부 조합 오류')}",
                "model": MODEL,
                "prompt_version": ver,
            })
            f.flush()


if __name__ == "__main__":
    main()
