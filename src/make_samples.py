import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "processed" / "kwic_snippets.csv"
OUT_DESIGN = ROOT / "data" / "processed" / "sample_design_20.csv"
OUT_VALID = ROOT / "data" / "processed" / "sample_validation_45.csv"
OUT_LABELS = ROOT / "data" / "labels" / "manual_labels_validation45.csv"

SEED = 20261115  # 시드 고정: 같은 조각이 다시 뽑히도록 하고 아래 존재 검사로 재추출도 막음
N_DESIGN, N_VALID = 20, 45


def write_new(frame, path):
    with open(path, "x", encoding="utf-8-sig", newline="") as f:  # 이미 있으면 예외
        frame.to_csv(f, index=False)


def main():
    for p in (OUT_DESIGN, OUT_VALID):
        if p.exists():
            sys.exit(f"중단: {p.name} 이미 존재. 재추출하면 설계/검증 표본이 섞일 수 있음")

    df = pd.read_csv(SRC)
    pool = df[~df.is_duplicate]

    # 한 번에 비복원 추출한 뒤 잘라 쓰므로 설계용과 검증용이 구조적으로 겹치지 않음
    picked = random.Random(SEED).sample(sorted(pool.snippet_id), N_DESIGN + N_VALID)
    design_ids, valid_ids = picked[:N_DESIGN], picked[N_DESIGN:]
    assert not set(design_ids) & set(valid_ids)

    by_id = df.set_index("snippet_id")
    write_new(by_id.loc[design_ids].reset_index(), OUT_DESIGN)
    # 블라인드용이라 시기·신문 메타와 LLM 라벨은 넣지 않음
    write_new(by_id.loc[valid_ids, ["snippet_clean", "snippet_raw"]].reset_index(), OUT_VALID)

    # 연구자가 채우는 파일이므로 이미 있으면 절대 건드리지 않음
    if not OUT_LABELS.exists():
        OUT_LABELS.parent.mkdir(parents=True, exist_ok=True)
        write_new(pd.DataFrame({"snippet_id": valid_ids, "human_category": "",
                                "human_sub_type": "", "memo": ""}), OUT_LABELS)

    for name, ids in (("설계", design_ids), ("검증", valid_ids)):
        cnt = by_id.loc[ids].groupby("period").size()
        print(name, {(f"{k} (4 yrs, n={v})" if k == "1960–63" else f"{k} (n={v})"): v for k, v in cnt.items()})
    low = by_id.loc[picked, "dict_ratio"] < 0.8
    print(f"추출 65개 중 dict_ratio<0.8: {int(low.sum())}개")


if __name__ == "__main__":
    main()
