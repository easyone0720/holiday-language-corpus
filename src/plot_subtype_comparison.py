"""가정·사교·공동체 vs 종교·기원 세부유형(각 2종)의 시기별 비율을 비교하는 그래프를 만든다.

- 입력(읽기 전용): data/processed/pred_full_v0.3.csv(AI 분류), kwic_snippets.csv(period). 병합 키는 snippet_id.
- 비율: 각 시기 전체 조각 수(n) 대비 해당 세부유형 건수(%). 1960–63은 4개년 표본이라 (4 yrs, n=71)로 표기.
- 검증: 병합 뒤 788건, 시기별 n, summary_period_subtype_v0.3.csv의 세부유형 건수와 일치하는지 확인한다.
- 저장: outputs/ppt_charts/slide13_family_vs_religion_subtypes.png (300 DPI). 이미 있으면 중단(--overwrite로만 갱신).
- --write 없이 실행하면 계산 결과만 출력한다. 한글 폰트가 없으면 깨진 그림을 만들지 않고 중단한다(--font-path 지정 가능).
"""
import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs" / "ppt_charts" / "slide13_family_vs_religion_subtypes.png"
PERIODS = ["1900s", "1910s", "1920s", "1930s", "1940s", "1950s", "1960–63"]
PANELS = [
    ("가정·사교·공동체", ["일상·사교형", "자선·나눔형"], ["#3D6B52", "#9DBBA8"], ["-", "--"], 100),
    ("종교·기원", ["예배·신학", "기원·역사해설"], ["#8B3A2B", "#D2A08F"], ["-", "--"], 50),
]
INK, MUTED, GRID, AXIS = "#3B2820", "#7A6A5E", "#EAE3D6", "#B8AC9C"
FONTS = ["Malgun Gothic", "맑은 고딕", "AppleGothic", "NanumGothic", "Nanum Gothic", "Noto Sans CJK KR", "Noto Sans KR"]


def load():
    pred = pd.read_csv(PROC / "pred_full_v0.3.csv", encoding="utf-8-sig")
    kwic = pd.read_csv(PROC / "kwic_snippets.csv", encoding="utf-8-sig")
    df = pred.merge(kwic[["snippet_id", "period"]], on="snippet_id", how="left", validate="one_to_one")
    assert len(df) == 788 and df.period.notna().all()
    n = df.groupby("period").size().reindex(PERIODS)
    assert n.tolist() == [137, 153, 114, 83, 88, 142, 71]
    cnt = df.groupby(["period", "sub_type"]).size().unstack(fill_value=0).reindex(PERIODS)
    ref = pd.read_csv(PROC / "summary_period_subtype_v0.3.csv", encoding="utf-8-sig").set_index("period")
    for _, subs, *_ in PANELS:
        for s in subs:
            assert cnt[s].tolist() == ref[f"n_{s}"].tolist(), f"{s}: 요약표와 건수가 다름"
    return n, cnt, cnt.div(n, axis=0) * 100


def find_font(path):
    if path:
        font_manager.fontManager.addfont(path)
        return font_manager.FontProperties(fname=path).get_name()
    have = {f.name for f in font_manager.fontManager.ttflist}
    for name in FONTS:
        if name in have:
            return name
    sys.exit("중단: 한글 폰트를 찾지 못함(--font-path로 지정)")


def draw(n, cnt, pct):
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.4), dpi=300)
    fig.patch.set_facecolor("white")
    xl = [f"{p}\n(4 yrs, n={n[p]})" if p == "1960–63" else f"{p}\n(n={n[p]})" for p in PERIODS]
    x = list(range(len(PERIODS)))
    for ax, (cat, subs, cols, styles, ymax) in zip(axes, PANELS):
        for xs in (2, 4):  # 1920s, 1940s 강조
            ax.axvspan(xs - 0.4, xs + 0.4, color="#F4EFE6", zorder=0)
        for s, c, ls in zip(subs, cols, styles):
            ax.plot(x, pct[s], color=c, ls=ls, lw=2.4, marker="o", ms=6.5, mfc="white" if ls == "--" else c, mec=c, mew=1.8, zorder=3, label=s)
            vals = pct[s].tolist()
            for xi in x:
                v, k = vals[xi], cnt[s].iloc[xi]
                left = vals[xi - 1] if xi > 0 else None
                right = vals[xi + 1] if xi < len(x) - 1 else None
                valley = cat == "가정·사교·공동체" and left is not None and right is not None and v < left and v < right  # 꺾이는 골짜기만 점 아래에 표기
                below = valley if ls == "-" else True
                dx, dy = 0, (-27 if below else 9)
                if cat == "가정·사교·공동체" and ls == "-" and xi == len(x) - 1:
                    dx, dy = 22, 9
                if cat == "종교·기원" and ls == "--" and xi == 4:  # 1940s: 두 선이 같은 값(20.5%)이라 라벨을 옆으로 비킴
                    dx, dy = 30, -8
                ax.annotate(f"{v:.1f}%\n({k}건)", (xi, v), textcoords="offset points", xytext=(dx, dy), ha="center", fontsize=7.6,
                            color=c if ls == "-" else MUTED, zorder=4)
        ax.set_ylim(-13, ymax)
        ax.set_yticks(range(0, ymax + 1, 20 if ymax == 100 else 10))
        ax.set_xlim(-0.5, len(x) - 0.5)
        ax.set_xticks(x)
        ax.set_xticklabels(xl, fontsize=8.2, color=INK)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
        ax.tick_params(axis="y", labelsize=8.5, colors=MUTED, length=0)
        ax.tick_params(axis="x", length=0)
        ax.grid(axis="y", color=GRID, lw=0.8, zorder=1)
        for sp in ("top", "right", "left"):
            ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_color(AXIS)
        ax.set_title(f"{cat}  (y축 0–{ymax}%)", fontsize=11.5, color=INK, fontweight="bold", loc="left", pad=10)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, fontsize=9.5, frameon=False, labelcolor=INK)
    fig.suptitle("일상·사교형이 기저를 이루고, 1920s·1940s에 예배·신학과 기원·역사해설이 함께 커진다", x=0.06, y=0.985, ha="left", fontsize=13.2, fontweight="bold", color=INK)
    fig.text(0.06, 0.918, "시기별 전체 조각 수 대비 세부유형 비율(%). 음영은 1920s·1940s. 패널마다 y축 눈금이 다름 · AI 분류(v0.3) 결과", fontsize=8.8, color=MUTED, ha="left")
    fig.subplots_adjust(left=0.06, right=0.985, top=0.80, bottom=0.2, wspace=0.12)
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--font-path")
    a = ap.parse_args()
    n, cnt, pct = load()
    cols = [s for _, subs, *_ in PANELS for s in subs]
    print(pd.concat([n.rename("n"), cnt[cols], pct[cols].round(1).add_suffix(" %")], axis=1).to_string())
    if not a.write:
        print(f"\n(저장 안 함) 저장 예정: {OUT}")
        return
    if OUT.exists() and not a.overwrite:
        sys.exit(f"중단: 이미 있는 파일이라 덮어쓰지 않음(--overwrite): {OUT}")
    plt.rcParams["font.family"] = find_font(a.font_path)
    plt.rcParams["axes.unicode_minus"] = False
    fig = draw(n, cnt, pct)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300, facecolor="white")
    print(f"\n저장: {OUT}")


if __name__ == "__main__":
    main()
