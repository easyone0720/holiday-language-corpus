"""발표용(PPT) 차트 이미지를 data/processed/의 실제 CSV로 그려 outputs/ppt_charts/에 저장한다.

- 읽기 전용: data/processed/의 CSV는 읽기만 하고 수정하지 않는다.
- --write 없이 실행하면 입력 점검과 저장 예정 목록만 출력한다.
- 저장할 파일이 이미 있으면 중단한다(덮어쓰기 방지). 의도적으로 갱신할 때만 --overwrite를 함께 쓴다.
- 팔레트: 빈티지 크리스마스 톤(아이보리 카드 위에 올리는 용도). 배경은 흰색, --transparent로 투명 저장 가능.
- 한글 폰트는 Malgun Gothic → AppleGothic → NanumGothic → Noto Sans CJK KR 순으로 찾고,
  없으면 글자가 깨진 그림을 만들지 않고 중단한다(--font-path로 직접 지정 가능).
- 표기 원칙: 건수(n)와 퍼센트(%)만 쓴다(출현 지면 수 등 DF 표기는 쓰지 않음).
"""
import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
DEFAULT_OUT = ROOT / "outputs" / "ppt_charts"
DPI = 300
FIG_W, FIG_H = 10.0, 5.6

CATS = ["종교·기원", "가정·사교·공동체", "상업·소비", "시사·기타"]
COLORS = {"종교·기원": "#8B3A2B", "가정·사교·공동체": "#3D6B52", "상업·소비": "#C8964E", "시사·기타": "#8C8279"}
# 앤틱 골드는 흰 글씨 대비가 낮아(약 2.6:1) 블록 안 글씨를 코코아 색으로 쓴다
COCOA = "#3B2820"
TEXT_ON = {"종교·기원": "white", "가정·사교·공동체": "white", "상업·소비": COCOA, "시사·기타": "white"}

BURGUNDY = "#732E24"   # 메인 강조
SAND = "#D8CCB8"       # 보조/일반 막대
GOLD_MUTED = "#C59B5F"  # 보조 막대(대안)
SAGE = "#6B8E78"       # 비교·탐색적 보정
SAGE_EDGE = "#4F6F5B"
INK, MUTED, GRID, AXIS = COCOA, "#7A6A5E", "#EAE3D6", "#B8AC9C"

FONT_CANDIDATES = ["Malgun Gothic", "맑은 고딕", "AppleGothic", "NanumGothic", "Nanum Gothic", "NanumBarunGothic", "Noto Sans CJK KR", "Noto Sans KR"]

FILES = [
    "slide05_period_counts.png",
    "slide08_version_accuracy.png",
    "slide09_overall_donut.png",
    "slide10_top10_ngrams.png",
    "slide12_period_category_stacked.png",
    "slide13_ngram_category_mapping.png",
    "slide13_top2_ngrams_period_trend.png",
    "slide16_low_confidence_by_period.png",
    "slide18_leave_extreme_out.png",
]
TOP2 = ["christmas day", "christmas tree"]
SMALL_N = 5  # 이 값 미만이면 비율 해석에 주의(흐린 막대)


def setup_font(font_path=None):
    if font_path:
        for fp in font_path:  # 보통체·굵은체 .ttf를 함께 줄 수 있음
            font_manager.fontManager.addfont(fp)
        name = font_manager.FontProperties(fname=font_path[0]).get_name()
    else:
        installed = {f.name for f in font_manager.fontManager.ttflist}
        name = next((c for c in FONT_CANDIDATES if c in installed), None)
    if not name:
        sys.exit("중단: 한글 폰트를 찾지 못함(Malgun Gothic/AppleGothic/NanumGothic/Noto Sans CJK KR). --font-path로 .ttf를 지정하세요.")
    plt.rcParams.update({
        "font.family": [name, "DejaVu Sans"],
        "axes.unicode_minus": False,  # 마이너스 기호 깨짐 방지
        "figure.facecolor": "white",
        "axes.facecolor": "none",
        "text.color": INK,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
    })
    return name


def read(name):
    p = PROC / name
    if not p.exists():
        sys.exit(f"중단: 입력 파일이 없음: {p}")
    return pd.read_csv(p, encoding="utf-8-sig")


def need(df, cols, name):
    miss = [c for c in cols if c not in df.columns]
    if miss:
        sys.exit(f"중단: {name}에 필요한 열이 없음: {miss} (실제 열: {list(df.columns)})")


def load():
    d = {
        "period": read("summary_period_category_v0.3.csv"),
        "overall": read("summary_overall_v0.3.csv"),
        "versions": read("summary_versions_v0.3.csv"),
        "conf": read("summary_period_confidence_v0.3.csv"),
        "freq": read("ngram_frequency_v0.3.csv"),
        "ngcat": read("ngram_category_v0.3.csv"),
        "inst": read("ngram_instances_v0.3.csv"),
        "leave": read("bias_adjusted_leave_extreme_out.csv"),
    }
    need(d["period"], ["period", "n", "n_pages"] + [f"pct_{c}" for c in CATS], "summary_period_category_v0.3.csv")
    need(d["overall"], ["section", "item", "n", "pct"], "summary_overall_v0.3.csv")
    need(d["versions"], ["version", "role", "source", "category_accuracy_pct", "cohen_kappa"], "summary_versions_v0.3.csv")
    need(d["conf"], ["period", "n", "n_low", "pct_low"], "summary_period_confidence_v0.3.csv")
    need(d["freq"], ["ngram", "n_snippets"], "ngram_frequency_v0.3.csv")
    need(d["ngcat"], ["ngram", "n_total"] + [f"pct_{c}" for c in CATS], "ngram_category_v0.3.csv")
    need(d["inst"], ["ngram", "snippet_id", "period", "category"], "ngram_instances_v0.3.csv")
    need(d["leave"], ["criterion", "k_excluded", "period", "n_pages_left", "pooled_pct_종교·기원"], "bias_adjusted_leave_extreme_out.csv")

    p = d["period"]
    assert len(p) == 7 and int(p.n.sum()) == 788, "시기 7개·조각 788건이 아님"
    assert ((p[[f"pct_{c}" for c in CATS]].sum(axis=1) - 100).abs() < 0.5).all(), "시기별 범주 비율 합이 100%가 아님"
    assert (d["conf"].set_index("period").n == p.set_index("period").n).all(), "시기별 n이 신뢰도 표와 다름"
    cat = d["overall"].query("section == 'category'").set_index("item")
    assert int(cat.n.sum()) == 788 and set(cat.index) == set(CATS), "전체 범주 분포가 788건이 아님"

    # 상위 2개 표현: ngram_instances(조각 단위)가 ngram_frequency·범주표와 같은 수인지 확인하고,
    # 있으면 표현별 문맥 파일(ngram_context_*)의 시기×범주 건수와도 대조한다
    fr = d["freq"].set_index("ngram")
    nc = d["ngcat"].set_index("ngram")
    inst = d["inst"]
    assert not inst.duplicated(["ngram", "snippet_id"]).any(), "ngram_instances에 중복 행"
    for name in TOP2:
        sub = inst[inst.ngram == name]
        assert len(sub) == int(fr.loc[name, "n_snippets"]) == int(nc.loc[name, "n_total"]), f"{name}: 조각 수가 파일 간에 다름"
        assert set(sub.category) <= set(CATS) and set(sub.period) <= set(p.period), f"{name}: 알 수 없는 범주·시기"
        ctx = PROC / f"ngram_context_{name.replace(' ', '_')}_v0.3.csv"
        if ctx.exists():
            c = pd.read_csv(ctx, encoding="utf-8-sig")
            need(c, ["period", "category"], ctx.name)
            a = pd.crosstab(sub.period, sub.category).reindex(index=p.period, columns=CATS, fill_value=0)
            b = pd.crosstab(c.period, c.category).reindex(index=p.period, columns=CATS, fill_value=0)
            assert (a.values == b.values).all(), f"{name}: ngram_instances와 {ctx.name}의 시기×범주 건수가 다름"
    return d


def xlabels(p):
    out = []
    for r in p.itertuples():
        out.append(f"{r.period}\n(4 yrs, n={r.n})" if r.period == "1960–63" else f"{r.period}\n(n={r.n})")
    return out


def base(ax, grid_axis="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(AXIS)
    ax.tick_params(length=0, labelsize=12)
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color=GRID, linewidth=1)


def title(ax, text, sub=None):
    ax.set_title(text, loc="left", fontsize=17, fontweight="bold", pad=26 if sub else 14)
    if sub:
        ax.text(0, 1.03, sub, transform=ax.transAxes, fontsize=11.5, color=MUTED, va="bottom")


def foot(fig, text):
    fig.text(0.01, -0.02, text, fontsize=10, color=MUTED, ha="left", va="top")


def cat_handles():
    return [plt.Rectangle((0, 0), 1, 1, color=COLORS[c]) for c in CATS]


def legend_below(ax, ncol=4):
    ax.legend(cat_handles(), CATS, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=ncol, frameon=False, fontsize=12, handlelength=1.2, columnspacing=1.6)


def new(figsize=(FIG_W, FIG_H)):
    return plt.subplots(figsize=figsize)


# ---------------------------------------------------------------- 차트
def c05(d):
    p = d["period"]
    fig, ax = new()
    bars = ax.bar(range(len(p)), p.n, color=BURGUNDY, width=0.62)
    for b, v in zip(bars, p.n):
        ax.text(b.get_x() + b.get_width() / 2, v + 2.5, f"{v}", ha="center", va="bottom", fontsize=14, fontweight="bold")
    ax.set_xticks(range(len(p)), xlabels(p))
    ax.set_ylim(0, p.n.max() * 1.15)
    ax.set_ylabel("문맥 조각 수")
    base(ax)
    title(ax, f"시기별 문맥 조각 수: 7개 시기 합계 n={int(p.n.sum())}", f"시기당 신문 지면 {int(p.n_pages.iloc[0])}개 표본 · 1960–63은 4개년 표본")
    return fig


def c08(d):
    v = d["versions"]
    v = v[(v.source == "검증 실행(45건)") & v.version.isin(["v0.1", "v0.2", "v0.3"])].sort_values("version")
    assert len(v) == 3, "검증 실행(45건) 행이 v0.1·v0.2·v0.3 3개가 아님"
    fig, ax = new()
    for i, r in enumerate(v.itertuples()):
        official = r.version == "v0.1"
        if official:
            ax.bar(i, r.category_accuracy_pct, 0.55, color=BURGUNDY)
        else:
            ax.bar(i, r.category_accuracy_pct, 0.55, color=SAGE, hatch="//", edgecolor=SAGE_EDGE, linewidth=1)
        ax.text(i, r.category_accuracy_pct + 1.5, f"{r.category_accuracy_pct:.1f}%", ha="center", fontsize=17, fontweight="bold")
        ax.text(i, r.category_accuracy_pct / 2, f"κ {r.cohen_kappa:.3f}", ha="center", va="center", fontsize=13, fontweight="bold",
                color="white" if official else INK, bbox=None if official else dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="none"))
    ax.set_xticks(range(3), [f"{r.version}\n{r.role}" for r in v.itertuples()], fontsize=13)
    ax.set_ylim(0, 105)
    ax.set_ylabel("범주 정확도(%)")
    base(ax)
    title(ax, "규칙을 고치며 정확도 변화: 공식 기준선 88.9% → 탐색적 91.1%", "연구자 정답 45건 대조 · v0.2·v0.3은 검증 표본을 본 뒤 보정한 탐색적 결과(빗금)")
    return fig


def c09(d):
    cat = d["overall"].query("section == 'category'").set_index("item").loc[CATS].sort_values("n", ascending=False)
    fig, ax = new()
    wedges, _ = ax.pie(cat.n, colors=[COLORS[c] for c in cat.index], startangle=90, counterclock=False, wedgeprops=dict(width=0.38, edgecolor="white", linewidth=3))
    ax.text(0, 0.06, f"n={int(cat.n.sum())}", ha="center", va="center", fontsize=26, fontweight="bold")
    ax.text(0, -0.14, "전체 문맥 조각", ha="center", va="center", fontsize=12, color=MUTED)
    for w, (name, r) in zip(wedges, cat.iterrows()):
        if r.pct >= 10:
            ang = np.deg2rad((w.theta1 + w.theta2) / 2)
            rr = 1 - 0.19
            ax.text(rr * np.cos(ang), rr * np.sin(ang), f"{r.pct:.1f}%", ha="center", va="center", fontsize=13, fontweight="bold", color=TEXT_ON[name])
    labels = [f"{c}  {r.pct:.1f}% (n={int(r.n)})" for c, r in cat.iterrows()]
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=COLORS[c]) for c in cat.index], labels, loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False, fontsize=14, labelspacing=1.1)
    ax.set_title("전체 788건의 4대 의미 범주: 가정·사교·공동체가 62.4%", loc="left", fontsize=17, fontweight="bold", pad=14)
    ax.set_aspect("equal")
    return fig


def c10(d):
    top = d["freq"].head(10).copy()
    fig, ax = new()
    y = list(range(len(top)))[::-1]
    ax.barh(y, top.n_snippets, color=[BURGUNDY if n in TOP2 else SAND for n in top.ngram], height=0.66)
    for yi, r in zip(y, top.itertuples()):
        ax.text(r.n_snippets + 0.8, yi, f"{r.n_snippets}", va="center", fontsize=13, fontweight="bold" if r.ngram in TOP2 else "normal")
    ax.set_yticks(y, top.ngram, fontsize=13)
    ax.set_xlim(0, top.n_snippets.max() * 1.15)
    ax.set_xlabel("표현이 나온 조각 수(n)")
    base(ax, "x")
    title(ax, "가장 많이 나온 표현은 christmas day(58)와 christmas tree(53)", "막대 끝: 해당 표현이 나온 조각 수")
    return fig


def stack_labels(ax, vals, bottoms, x, color_key, min_v, fmt, horizontal=False, fs=11.5):
    for xi, v, bt in zip(x, vals, bottoms):
        if v >= min_v:
            if horizontal:
                ax.text(bt + v / 2, xi, fmt(v), ha="center", va="center", fontsize=fs, fontweight="bold", color=TEXT_ON[color_key])
            else:
                ax.text(xi, bt + v / 2, fmt(v), ha="center", va="center", fontsize=fs, fontweight="bold", color=TEXT_ON[color_key])


def c12(d):
    p = d["period"]
    fig, ax = new()
    bottom = pd.Series(0.0, index=p.index)
    x = list(range(len(p)))
    for c in CATS:
        vals = p[f"pct_{c}"]
        ax.bar(x, vals, 0.66, bottom=bottom, color=COLORS[c], edgecolor="white", linewidth=1.8)
        stack_labels(ax, vals, bottom, x, c, 5.5, lambda v: f"{v:.1f}%")
        bottom += vals
    ax.set_xticks(x, xlabels(p))
    ax.set_ylim(0, 100)
    ax.set_yticks(range(0, 101, 20), [f"{t}%" for t in range(0, 101, 20)])
    base(ax)
    legend_below(ax)
    title(ax, "시기별 4대 범주: 한 방향이 아니라 오르내림", "시기당 5개 지면 표본이라 일부 변동은 지면 차이일 수 있음")
    return fig


def c13(d):
    order = ["christmas day", "christmas tree", "christmas eve", "passed christmas", "spent christmas", "merry christmas"]
    g = d["ngcat"].set_index("ngram").loc[order]
    fig, ax = new()
    y = list(range(len(order)))[::-1]
    left = pd.Series(0.0, index=g.index)
    for c in CATS:
        vals = g[f"pct_{c}"]
        ax.barh(y, vals, left=left, height=0.62, color=COLORS[c], edgecolor="white", linewidth=1.8)
        stack_labels(ax, vals, left, y, c, 8, lambda v: f"{v:.1f}%", horizontal=True)
        left += vals
    ax.set_yticks(y, [f"{n}  (n={int(g.loc[n, 'n_total'])})" for n in order], fontsize=12.5)
    ax.set_xlim(0, 100)
    ax.set_xticks(range(0, 101, 20), [f"{t}%" for t in range(0, 101, 20)])
    base(ax, "x")
    legend_below(ax)
    title(ax, "표현마다 맥락이 다르다: merry christmas만 상업·소비가 절반", "표현과 범주의 대응은 일관성 점검이며 독립 증거는 아님(같은 조각에서 범주를 정했기 때문)")
    return fig


def c13_trend(d):
    p = d["period"]
    periods = p.period.tolist()
    inst = d["inst"]
    fig, axes = plt.subplots(1, 2, figsize=(FIG_W + 2.4, FIG_H), sharey=True)
    xt = [pp if pp != "1960–63" else "1960–63\n(4 yrs)" for pp in periods]
    x = list(range(len(periods)))
    for ax, name in zip(axes, TOP2):
        sub = inst[inst.ngram == name]
        ct = pd.crosstab(sub.period, sub.category).reindex(index=periods, columns=CATS, fill_value=0)
        n = ct.sum(axis=1)
        pct = ct.div(n.replace(0, np.nan), axis=0).fillna(0) * 100
        bottom = pd.Series(0.0, index=pct.index)
        for c in CATS:
            vals = pct[c]
            for xi, v, bt, nn in zip(x, vals, bottom, n):
                if v > 0:
                    ax.bar(xi, v, 0.7, bottom=bt, color=COLORS[c], edgecolor="white", linewidth=1.5, alpha=0.5 if nn < SMALL_N else 1.0)
                    if v >= 16 and nn >= SMALL_N:
                        ax.text(xi, bt + v / 2, f"{v:.0f}%", ha="center", va="center", fontsize=10, fontweight="bold", color=TEXT_ON[c])
            bottom += vals
        for xi, nn in zip(x, n):
            ax.text(xi, 102, f"n={int(nn)}", ha="center", va="bottom", fontsize=11.5, fontweight="bold" if nn >= SMALL_N else "normal", color=INK if nn >= SMALL_N else MUTED)
        ax.set_xticks(x, xt, fontsize=11)
        ax.set_ylim(0, 112)
        ax.set_yticks(range(0, 101, 20), [f"{t}%" for t in range(0, 101, 20)])
        ax.set_title(f"{name} (n={len(sub)})", loc="left", fontsize=15, fontweight="bold", pad=10)
        base(ax)
    fig.legend(cat_handles(), CATS, loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=4, frameon=False, fontsize=12, handlelength=1.2, columnspacing=1.6)
    fig.tight_layout(rect=[0, 0.07, 1, 0.84])
    fig.text(0.01, 0.985, "핵심 두 표현의 시기별 4대 범주 비율", fontsize=17, fontweight="bold", ha="left", va="top")
    fig.text(0.01, 0.915, "막대 위 n: 해당 시기에 그 표현이 나온 조각 수 · 흐린 막대는 n이 5 미만이라 비율 해석에 주의", fontsize=11.5, color=MUTED, ha="left", va="top")
    return fig


def c16(d):
    c = d["conf"]
    avg = float(d["overall"].query("section == 'confidence' and item == 'low'").iloc[0].pct)
    fig, ax = new()
    bars = ax.bar(range(len(c)), c.pct_low, 0.62, color=[BURGUNDY if v > avg else GOLD_MUTED for v in c.pct_low])
    for bb, r in zip(bars, c.itertuples()):
        ax.text(bb.get_x() + bb.get_width() / 2, r.pct_low + 0.8, f"{r.pct_low:.1f}%\n(n={int(r.n_low)})", ha="center", va="bottom", fontsize=12.5, fontweight="bold", zorder=5, bbox=dict(facecolor="white", edgecolor="none", pad=1.5))
    ax.axhline(avg, color=INK, linestyle=(0, (4, 3)), linewidth=1.6)
    ax.text(-0.45, avg + 0.8, f"전체 평균 {avg:.1f}%", ha="left", va="bottom", fontsize=12, color=INK)
    ax.set_xticks(range(len(c)), xlabels(c))
    ax.set_ylim(0, c.pct_low.max() * 1.28)
    ax.set_ylabel("저신뢰(low) 조각 비중(%)")
    base(ax)
    title(ax, "저신뢰 사례는 1920s·1940s에 몰림", "AI가 확신이 낮다고 표시한 조각의 시기별 비중 · 버건디 막대는 전체 평균보다 높은 시기")
    return fig


def c18(d):
    L = d["leave"]
    panels = [("concentration", "집중도 기준\n(한 범주 몰림이 큰 지면부터 제외)"), ("volume", "조각 수 기준\n(조각이 많은 지면부터 제외)")]
    ks = [0, 1, 3, 5]
    fig, axes = plt.subplots(1, 2, figsize=(FIG_W, FIG_H), sharey=True)
    series = [("1930s", "-", "o", COLORS["종교·기원"]), ("1910s", (0, (5, 3)), "s", "#C79A91")]
    left_pages = {}
    for ax, (crit, ttl) in zip(axes, panels):
        for per, ls, mk, col in series:
            s = L[(L.criterion == crit) & (L.period == per)].set_index("k_excluded").loc[ks]
            v = s["pooled_pct_종교·기원"].values
            ax.plot(range(4), v, color=col, linestyle=ls, marker=mk, markersize=8, linewidth=2.6)
            ax.text(3.12, v[-1], f"{per}\n{v[-1]:.1f}%", va="center", fontsize=12, color=INK, fontweight="bold")
            ax.text(0, v[0] + 1.3, f"{v[0]:.1f}%", va="bottom", ha="center", fontsize=11, color=MUTED)
            if crit == "concentration":
                left_pages[per] = int(s.loc[5, "n_pages_left"])
        ax.set_xticks(range(4), [str(k) for k in ks])
        ax.set_xlim(-0.55, 3.9)
        ax.set_xlabel("제외한 극단 지면 수")
        ax.set_title(ttl, loc="left", fontsize=12.5, color=INK)
        base(ax)
    axes[0].set_ylabel("종교·기원 비율(%, 합산)")
    axes[0].set_ylim(0, 35)
    fig.suptitle("극단 지면을 빼면 시기 비율이 달라진다: 1930s 종교·기원 8.4% → 28.0%", x=0.01, ha="left", fontsize=17, fontweight="bold", y=1.03)
    fig.tight_layout()
    foot(fig, f"집중도 기준 5개 제외 후 남는 지면: 1930s {left_pages['1930s']}개, 1910s {left_pages['1910s']}개(시기당 5개 중). 남는 지면이 적을수록 해석에 주의.")
    return fig


CHARTS = [c05, c08, c09, c10, c12, c13, c13_trend, c16, c18]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="PNG를 저장(없으면 점검만)")
    ap.add_argument("--overwrite", action="store_true", help="이미 있는 PNG를 의도적으로 갱신할 때만 사용")
    ap.add_argument("--transparent", action="store_true", help="배경을 투명으로 저장(기본은 흰색)")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--font-path", nargs="+", default=None, help="한글 .ttf 경로(보통체, 굵은체 순; 자동 탐지 실패 시)")
    a = ap.parse_args()
    assert len(CHARTS) == len(FILES)

    font = setup_font(a.font_path)
    d = load()
    print(f"입력 점검 통과(시기 7개·788건·범주 합 100%·상위 2개 표현 건수 일치). 한글 폰트: {font}")
    paths = [a.out_dir / f for f in FILES]
    if not a.write:
        print("저장 예정(--write 없음, 저장 안 함):")
        for p in paths:
            print("  ", p, "(이미 있음)" if p.exists() else "")
        return
    clash = [str(p) for p in paths if p.exists()]
    if clash and not a.overwrite:
        sys.exit("중단: 이미 존재하는 파일이 있어 덮어쓰지 않음(갱신하려면 --overwrite)\n  " + "\n  ".join(clash))
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for fn, p in zip(CHARTS, paths):
        fig = fn(d)
        fig.savefig(p, dpi=DPI, bbox_inches="tight", facecolor="white", transparent=a.transparent)
        plt.close(fig)
        h, w = plt.imread(p).shape[:2]
        print(f"저장: {p}  ({w}x{h}px, {p.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()
