import argparse
import csv
import os
import sys
import time
from pathlib import Path

import anthropic
import pandas as pd
from dotenv import load_dotenv

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

EDGE_RULES_V3 = """
EDGE-CASE RULES
1. Holiday greeting ads. A message that carries a named business or its proprietor and wishes customers or townspeople "Merry Christmas" or "Happy New Year", or thanks them for their patronage, is an advertisement even when it names no goods, prices or discounts. Always 상업·소비/판촉·광고형.
2. Who presents the program. When a church, Sunday school or other religious body presents or announces the Christmas program or services (an order of exercises with hymns, carols, Scripture readings, recitations, a pageant or nativity play, or a notice of services or Mass), classify it 종교·기원/예배·신학, even if children perform and even if a tree or gifts are also mentioned.
3. Secular community scenes. Parties, trees, parades, entertainments and caroling organised by schools, clubs, workplaces, hospitals or civic bodies, with no religious body presenting and no worship focus, are 가정·사교·공동체/일상·사교형. Naming a church or a Catholic hospital only as a place or background does not make an excerpt religious.
4. Mixed passages. If a religious rite or sacred imagery (Mass, holy pictures, the nativity) sits beside festivity, decide by what the text dwells on closest to the keyword, and set confidence to medium or low.
5. Worship versus origins. 예배·신학 covers Christmas service programs, Mass settings, offertory anthems, Christmas hymns, and devout or lyrical poems and songs that praise the birth of Jesus. 기원·역사해설 covers only writing that explains the historical or folkloric origin of customs such as the tree, Santa Claus or the date of December 25.
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
# v0.3은 v0.2의 오답을 본 뒤 만든 탐색용 버전이라 45건 수치는 낙관적일 수 있다
TIE_BREAKS_V3 = TIE_BREAKS.replace(
    "- School/community Christmas programs (recitations, songs, pageants) are 일상·사교형 unless the focus is worship or doctrine.",
    "- School, club and civic Christmas programs are 일상·사교형 unless a church or religious body presents them or the focus is worship or doctrine.",
)
assert TIE_BREAKS_V3 != TIE_BREAKS
PROMPTS["v0.3-presenter-rule"] = HEAD_V2 + DEFINITIONS + EDGE_RULES_V3 + "\nOTHER TIE-BREAKS\n" + TIE_BREAKS_V3

TOOL = {
    "name": "record_label",
    "description": "Record the classification of one excerpt.",
    "strict": True,  # tool_choice를 강제할 수 없는 모델이라 스키마 준수는 strict로 보장
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
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


RETRYABLE = (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.InternalServerError)


def classify(client, system, text):
    err = None
    for attempt in range(5):
        try:
            # Sonnet 5.5는 tool/any 강제와 기본값이 아닌 temperature를 400으로 거부한다(재실행 시 라벨이 달라질 수 있음)
            # thinking을 생략하면 기본으로 켜지고 그 토큰도 max_tokens에 들어가므로 넉넉히 잡는다
            r = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=system,
                tools=[TOOL],
                tool_choice={"type": "auto"},
                messages=[{
                    "role": "user",
                    "content": f"<excerpt>\n{text}\n</excerpt>\n\nClassify this excerpt by calling the record_label tool.",
                }],
            )
            block = next((b for b in r.content if b.type == "tool_use"), None)
            return block.input if block else {"error": f"tool_use 없음(stop_reason={r.stop_reason})"}
        except RETRYABLE as e:  # 일시적 오류만 재시도. 인자 오류·인증 오류·4xx는 바로 중단
            err = e
            time.sleep(2 ** attempt)
    return {"error": str(err)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-version", required=True, choices=list(PROMPTS))
    ap.add_argument("--input", default=str(ROOT / "data/processed/sample_validation_45.csv"))
    ap.add_argument("--output", "--out", help="기본값: data/processed/pred_validation_<v0.1|v0.2>.csv")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--resume", action="store_true", help="기존 출력의 ok 행은 유지하고 나머지(CHECK·미처리)만 이어서 분류")
    ap.add_argument("--dry-run", action="store_true", help="API 호출 없이 입력 건수와 출력 경로만 확인")
    a = ap.parse_args()

    ver = a.prompt_version
    out_path = Path(a.output) if a.output else ROOT / "data" / "processed" / f"pred_validation_{ver.split('-')[0]}.csv"
    if out_path.exists() and not a.resume:
        sys.exit(f"중단: {out_path} 이미 존재(덮어쓰기 금지). 이어서 돌리려면 --resume, 새로 돌리려면 --output을 새로 지정")
    if a.resume and not out_path.exists():
        sys.exit(f"중단: --resume인데 {out_path}가 없음")

    df = pd.read_csv(a.input, encoding="utf-8-sig")
    if "is_duplicate" in df:
        df = df[~df.is_duplicate]
    if a.limit:
        df = df.head(a.limit)

    done = []
    if a.resume:
        prev = pd.read_csv(out_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        if set(prev.get("prompt_version", [])) - {ver} or set(prev.get("model", [])) - {MODEL}:
            sys.exit("중단: 기존 출력의 프롬프트 버전 또는 모델이 현재 설정과 다름(섞어 쓰지 않음)")
        done = prev[prev.status == "ok"]
        df = df[~df.snippet_id.isin(done.snippet_id)]

    if a.dry_run:
        print(f"처리 대상 {len(df)}건(이미 ok {len(done)}건) | 출력 {out_path} | 프롬프트 {ver} | 모델 {MODEL}")
        return
    load_dotenv(ROOT / ".env")  # 이미 설정된 환경변수가 있으면 그 값을 우선(덮어쓰지 않음)
    if "ANTHROPIC_API_KEY" not in os.environ:
        sys.exit("ANTHROPIC_API_KEY가 필요합니다(루트의 .env 또는 환경변수)")

    # 프롬프트 튜닝은 sample_design_20만 사용. 검증 표본을 보고 고친 버전은 결과에 그 사실을 밝힐 것
    # 연도·신문명은 보내지 않아 가설 방향으로 쏠리는 것을 막음
    client = anthropic.Anthropic()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fails = n = 0
    if a.resume:  # CHECK 행은 버리고 ok 행만 남긴 뒤 이어쓴다(임시 파일로 바꿔치기)
        tmp = out_path.with_suffix(".tmp")
        done.to_csv(tmp, index=False, encoding="utf-8-sig")
        os.replace(tmp, out_path)
    try:
        with open(out_path, "a" if a.resume else "x", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            if not a.resume:
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
                n += 1
                if n % 50 == 0:
                    print(f"{n}/{len(df)}", flush=True)
                fails = 0 if ok else fails + 1
                if fails >= 3:  # 같은 문제로 계속 실패하는 것을 막아 호출 낭비와 불량 파일을 방지
                    raise RuntimeError(f"연속 3건 실패: {out.get('error', '범주/세부 조합 오류')}")
    except BaseException:
        print(f"중단됨: {out_path}에 지금까지의 결과를 남김. 같은 명령에 --resume을 붙여 이어서 실행", file=sys.stderr)
        raise
    res = pd.read_csv(out_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    print(f"완료: 전체 {len(res)}행 | ok {(res.status == 'ok').sum()} | CHECK {(res.status != 'ok').sum()}")


if __name__ == "__main__":
    main()
