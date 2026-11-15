"""발표용(PPT) 차트 이미지를 data/processed/의 실제 CSV로 그려 outputs/ppt_charts/에 저장한다.

- 읽기 전용: data/processed/의 CSV는 읽기만 하고 수정하지 않는다.
- --write 없이 실행하면 입력 점검과 저장 예정 목록만 출력한다.
- 저장할 파일이 이미 있으면 중단한다(덮어쓰기 방지). 의도적으로 갱신할 때만 --overwrite를 함께 쓴다.
- 팔레트: 빈티지 크리스마스 톤(아이보리 카드 위에 올리는 용도). 배경은 흰색, --transparent로 투명 저장 가능.
- 한글 폰트는 Malgun Gothic → AppleGothic → NanumGothic → Noto Sans CJK KR 순으로 찾고,
  없으면 글자가 깨진 그림을 만들지 않고 중단한다(--font-path로 직접 지정 가능).
- 표기 원칙: 건수(n)·비중(%)·등장 신문 면 수처럼 청중이 바로 읽는 말만 쓴다(DF 같은 약어 없음).
- 차트 구성(형태가 주제에 맞게 다름): 롤리팝(5쪽) · 기울기 그래프(8쪽) · 도넛(9쪽) · 산점도(10쪽) ·
  100% 누적 영역(12쪽) · 히트맵(13쪽) · 2단 누적 막대(핵심 표현 추이) · 선+영역과 지표 요약(16쪽) · 선(18쪽, 기존 유지)
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
from matplotlib.colors import LinearSegmentedColormap, PowerNorm
from matplotlib.patches import Rectangle

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
SAND = "#D8CCB8"       # 보조/일반
GOLD_MUTED = "#C59B5F"  # 보조(대안)
SAGE = "#6B8E78"       # 비교·탐색적 보정
SAGE_EDGE = "#4F6F5B"
INK, MUTED, GRID, AXIS = COCOA, "#7A6A5E", "#EAE3D6", "#B8AC9C"

FONT_CANDIDATES = ["Malgun Gothic", "맑은 고딕", "AppleGothic", "NanumGothic", "Nanum Gothic", "NanumBarunGothic", "Noto Sans CJK KR", "Noto Sans KR"]

# (파일명, 함수 이름) 순서 = 저장 순서
FILES = [
    "slide05_period_counts.png",
    "slide08_version_slope.png",
    "slide09_overall_donut.png",
    "slide10_ngram_scatter.png",
    "slide12_period_category_area.png",
    "slide13_subtype_heatmap.png",
    "slide13_top2_ngrams_period_trend.png",
    "slide16_validation_summary.png",
    "slide18_leave_extreme_out.png",
]
TOP2 = ["christmas day", "christmas tree"]
SMALL_N = 5  # 이 값 미만이면 비율 해석에 주의(흐린 막대)
N_PAGES_TOTAL = 35

SUBTYPE_ORDER = ["일상·사교형", "자선·나눔형", "예배·신학", "기원·역사해설", "판촉·광고형", "상업화 비판·성찰형", "시사·단신"]
SUBTYPE_CAT = {"일상·사교형": "가정·사교·공동체", "자선·나눔형": "가정·사교·공동체", "예배·신학": "종교·기원", "기원·역사해설": "종교·기원",
               "판촉·광고형": "상업·소비", "상업화 비판·성찰형": "상업·소비", "시사·단신": "시사·기타"}
CONFUSION = {"v0.1": "eval_confusion_v0.1-draft.csv", "v0.2": "eval_confusion_v0.2-edge-rules.csv", "v0.3": "eval_confusion_v0.3-presenter-rule.csv"}


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
    return pd.read_csv(p, encoding="utf-8-sig", index_col=None)


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
        "sub": read("summary_period_subtype_v0.3.csv"),
        "repro": read("summary_reproducibility_v0.3.csv"),
        "pred": read("pred_full_v0.3.csv"),
        "conf_mat": {v: read(f) for v, f in CONFUSION.items()},
    }
    need(d["period"], ["period", "n", "n_pages"] + [f"pct_{c}" for c in CATS], "summary_period_category_v0.3.csv")
    need(d["overall"], ["section", "item", "n", "pct"], "summary_overall_v0.3.csv")
    need(d["versions"], ["version", "role", "source", "category_accuracy_pct", "cohen_kappa"], "summary_versions_v0.3.csv")
    need(d["conf"], ["period", "n", "n_low", "pct_low"], "summary_period_confidence_v0.3.csv")
    need(d["freq"], ["ngram", "n_snippets"], "ngram_frequency_v0.3.csv")
    need(d["ngcat"], ["ngram", "n_total"] + [f"pct_{c}" for c in CATS], "ngram_category_v0.3.csv")
    need(d["inst"], ["ngram", "snippet_id", "period", "page_id", "category"], "ngram_instances_v0.3.csv")
    need(d["leave"], ["criterion", "k_excluded", "period", "n_pages_left", "pooled_pct_종교·기원"], "bias_adjusted_leave_extreme_out.csv")
    need(d["sub"], ["period", "n"] + [f"n_{s}" for s in SUBTYPE_ORDER] + [f"pct_{s}" for s in SUBTYPE_ORDER], "summary_period_subtype_v0.3.csv")
    need(d["repro"], ["metric", "n", "n_match", "agreement_pct"], "summary_reproducibility_v0.3.csv")
    need(d["pred"], ["snippet_id", "category", "sub_type"], "pred_full_v0.3.csv")

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

    # 세부유형 히트맵: 7개 유형이 하위 범주 합과 맞는지, 유형→범주 대응이 실제 분류 결과와 같은지 확인
    s = d["sub"]
    assert len(s) == 7 and int(s.n.sum()) == 788, "세부유형 표가 7개 시기·788건이 아님"
    assert (s[[f"n_{x}" for x in SUBTYPE_ORDER]].sum(axis=1) == s.n).all(), "세부유형 건수 합이 시기별 n과 다름"
    pair = d["pred"].drop_duplicates(["category", "sub_type"]).set_index("sub_type").category.to_dict()
    assert pair == SUBTYPE_CAT, f"세부유형→범주 대응이 분류 결과와 다름: {pair}"
    ps = p.set_index("period")
    for r in s.itertuples(index=False):
        row = dict(zip(s.columns, r))
        for c in CATS:
            m = sum(row[f"pct_{x}"] for x in SUBTYPE_ORDER if SUBTYPE_CAT[x] == c)
            assert abs(m - ps.loc[row["period"], f"pct_{c}"]) < 0.25, f"{row['period']} {c}: 세부유형 합계가 범주 비율과 다름"

    # 기울기 그래프: 혼동행렬에서 정확도·종교·기원 재현율을 직접 계산하고 versions 표의 정확도와 대조
    rec = {}
    vv = d["versions"][d["versions"].source == "검증 실행(45건)"].set_index("version")
    for v, cm in d["conf_mat"].items():
        cm = cm.set_index("human_category").loc[CATS, CATS]
        tot = int(cm.values.sum())
        acc = float(np.trace(cm.values)) / tot * 100
        assert tot == 45 and abs(acc - float(vv.loc[v, "category_accuracy_pct"])) < 0.06, f"{v}: 혼동행렬 정확도가 summary_versions와 다름"
        hit, human = int(cm.loc["종교·기원", "종교·기원"]), int(cm.loc["종교·기원"].sum())
        rec[v] = (hit, human)
    d["recall"] = rec

    # 산점도: 표현별 등장 신문 면 수는 ngram_instances의 page_id로 계산
    top = d["freq"].head(10)
    g = inst.groupby("ngram").agg(n=("snippet_id", "nunique"), pages=("page_id", "nunique"))
    d["scatter"] = g.loc[top.ngram].reset_index()
    assert (d["scatter"].n.values == top.n_snippets.values).all(), "상위 10개 표현 건수가 ngram_frequency와 다름"
    assert inst.page_id.nunique() == N_PAGES_TOTAL and int(d["scatter"].pages.max()) <= N_PAGES_TOTAL
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


def legend_below(ax, ncol=4, y=-0.16):
    ax.legend(cat_handles(), CATS, loc="upper center", bbox_to_anchor=(0.5, y), ncol=ncol, frameon=False, fontsize=12, handlelength=1.2, columnspacing=1.6)


def new(figsize=(FIG_W, FIG_H)):
    return plt.subplots(figsize=figsize)


def label_box(**kw):
    return dict(facecolor="white", edgecolor="none", pad=1.5, **kw)


# ---------------------------------------------------------------- 차트
def c05(d):
    """5쪽: 롤리팝 — 시기별 문맥 조각 수."""
    p = d["period"]
    x = np.arange(len(p))
    fig, ax = new()
    ax.vlines(x, 0, p.n, color=BURGUNDY, linewidth=3, zorder=2)
    ax.scatter(x, p.n, s=420, color=BURGUNDY, zorder=3, edgecolor="white", linewidth=2)
    for xi, v in zip(x, p.n):
        ax.text(xi, v + 9, f"{v}", ha="center", va="bottom", fontsize=15, fontweight="bold")
    ax.set_xticks(x, xlabels(p))
    ax.set_xlim(-0.6, len(p) - 0.4)
    ax.set_ylim(0, p.n.max() * 1.2)
    ax.set_ylabel("문맥 조각 수")
    base(ax)
    title(ax, f"시기별 문맥 조각 수: 7개 시기 합계 n={int(p.n.sum())}", f"시기당 신문 지면 {int(p.n_pages.iloc[0])}개 표본 · 1960–63은 4개년 표본")
    return fig


def c08(d):
    """8쪽: 기울기 그래프 — 정확도와 종교·기원 재현율이 v0.1→v0.3으로 변한 궤적."""
    v = d["versions"]
    v = v[(v.source == "검증 실행(45건)") & v.version.isin(["v0.1", "v0.2", "v0.3"])].sort_values("version")
    assert len(v) == 3, "검증 실행(45건) 행이 v0.1·v0.2·v0.3 3개가 아님"
    acc = v.category_accuracy_pct.tolist()
    kap = v.cohen_kappa.tolist()
    rec = [d["recall"][k][0] / d["recall"][k][1] * 100 for k in ["v0.1", "v0.2", "v0.3"]]
    cnt = [d["recall"][k] for k in ["v0.1", "v0.2", "v0.3"]]
    x = [0, 1, 2]
    fig, ax = new()
    for ys, col in ((acc, BURGUNDY), (rec, SAGE)):
        ax.plot(x[:2], ys[:2], color=col, linewidth=3, linestyle=(0, (5, 3)), zorder=2)  # 탐색적 구간은 점선
        ax.plot(x[1:], ys[1:], color=col, linewidth=3, linestyle=(0, (5, 3)), zorder=2)
        ax.scatter([0], [ys[0]], s=190, color=col, zorder=4, edgecolor="white", linewidth=1.5)  # 공식 기준선: 채운 점
        ax.scatter([1, 2], ys[1:], s=190, color="white", zorder=4, edgecolor=col, linewidth=3)  # 탐색적: 빈 점
    for xi, a, kp in zip(x, acc, kap):
        ax.text(xi, a + 3.2, f"{a:.1f}%", ha="center", fontsize=16, fontweight="bold", color=BURGUNDY)
    for xi, r, (h, m) in zip(x, rec, cnt):
        ax.text(xi, r - 6.2, f"{r:.1f}%\n({h}/{m}건)", ha="center", va="top", fontsize=12.5, fontweight="bold", color=SAGE_EDGE)
    ax.text(2.1, acc[2], "범주 정확도", va="center", fontsize=13, fontweight="bold", color=BURGUNDY)
    ax.text(2.1, rec[2], "종교·기원\n재현율", va="center", fontsize=13, fontweight="bold", color=SAGE_EDGE)
    ax.set_xticks(x, [f"{r.version} {r.role.split('(')[0]}\nκ={r.cohen_kappa:.3f}" for r in v.itertuples()], fontsize=12.5)
    ax.set_xlim(-0.35, 2.75)
    ax.set_ylim(20, 105)
    ax.set_yticks(range(20, 101, 20), [f"{t}%" for t in range(20, 101, 20)])
    base(ax)
    title(ax, "규칙을 고치며 달라진 점: 정확도 88.9% → 91.1%, 종교·기원 재현율 50% → 75%",
          "연구자 정답 45건 대조 · 실선 점=공식 기준선, 빈 점·점선=검증 표본을 본 뒤 보정한 탐색적 결과")
    foot(fig, "재현율 = 연구자가 종교·기원으로 본 8건 중 AI도 종교·기원으로 분류한 비율. 8건 기준이라 1건 차이가 12.5%p이므로 방향만 참고.")
    return fig


def c09(d):
    """9쪽: 도넛 — 전체 4대 범주 비중."""
    cat = d["overall"].query("section == 'category'").set_index("item").loc[CATS].sort_values("n", ascending=False)
    fig, ax = new()
    wedges, _ = ax.pie(cat.n, colors=[COLORS[c] for c in cat.index], startangle=90, counterclock=False, wedgeprops=dict(width=0.38, edgecolor="white", linewidth=3))
    ax.text(0, 0.06, f"총 {int(cat.n.sum())}건", ha="center", va="center", fontsize=26, fontweight="bold")
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
    """10쪽: 산점도 — 표현별 등장 건수(가로)와 등장한 신문 면 수(세로)."""
    s = d["scatter"]
    fig, ax = new()
    hi = s.ngram.isin(TOP2)
    sale = s.ngram == "christmas sale"
    colors = [BURGUNDY if h else (GOLD_MUTED if sl else SAND) for h, sl in zip(hi, sale)]
    edge = [BURGUNDY if h else (GOLD_MUTED if sl else AXIS) for h, sl in zip(hi, sale)]
    ax.scatter(s.n, s.pages, s=[520 if h or sl else 330 for h, sl in zip(hi, sale)], color=colors, edgecolor="white", linewidth=2, zorder=3)
    off = {  # (dx, dy, ha) — 점이 겹치는 곳(christmas day·tree·eve)은 방향을 나눠 배치
        "christmas day": (2.0, -1.5, "left"), "christmas tree": (-2.0, 1.4, "right"), "christmas eve": (0.0, -1.9, "center"),
        "passed christmas": (1.8, 0.0, "left"), "spent christmas": (1.8, 0.2, "left"), "merry christmas": (-1.8, 0.0, "right"),
        "christmas party": (1.8, -0.5, "left"), "christmas vacation": (1.8, 0.5, "left"), "christmas sale": (1.8, 0.0, "left"),
        "christmas dinner": (-1.0, -1.9, "left"),
    }
    for r in s.itertuples():
        dx, dy, ha = off[r.ngram]
        strong = r.ngram in TOP2 or r.ngram == "christmas sale"
        ax.text(r.n + dx, r.pages + dy, f"{r.ngram} ({r.n}건·{r.pages}면)", ha=ha, va="center", fontsize=12 if strong else 11, fontweight="bold" if strong else "normal", color=INK if strong else MUTED)
    ax.set_xlim(0, 78)
    ax.set_ylim(0, N_PAGES_TOTAL + 1)
    ax.axhline(N_PAGES_TOTAL, color=AXIS, linewidth=1, linestyle=(0, (2, 3)))
    ax.text(77.5, N_PAGES_TOTAL - 0.6, f"전체 {N_PAGES_TOTAL}면", ha="right", va="top", fontsize=10.5, color=MUTED)
    ax.set_xlabel("표현이 나온 총 건수(n)")
    ax.set_ylabel("표현이 나온 신문 지면 수(면)")
    base(ax, "both")
    sale_page = d["inst"].query("ngram == 'christmas sale'").page_id.iloc[0].split("_")[0]
    assert int(s.set_index("ngram").loc["christmas sale", "pages"]) == 1
    ax.annotate(f"한 면(광고 지면 {sale_page})에만 몰림", xy=(17.8, 1.4), xytext=(24, 4.0), fontsize=11.5, color=INK, fontweight="bold",
                arrowprops=dict(arrowstyle="-", color=GOLD_MUTED, linewidth=1.6), va="center")
    ax.text(60, 25.8, "건수도 많고\n여러 면에 고르게 등장", ha="center", fontsize=11.5, color=BURGUNDY, fontweight="bold")
    title(ax, "많이 나온 표현도 두 종류: 여러 면에 퍼진 표현 vs 한 면에 몰린 표현", "상위 10개 표현 · 오른쪽 위=건수도 많고 지면도 다양(christmas day·tree), 오른쪽 아래=건수는 많지만 한 면 집중(christmas sale)")
    return fig


def c12(d):
    """12쪽(메인): 100% 누적 영역 — 시기별 4대 범주 비중의 오르내림."""
    p = d["period"]
    x = np.arange(len(p))
    fig, ax = new((FIG_W, FIG_H + 0.2))
    ys = [p[f"pct_{c}"].values for c in CATS]
    ax.stackplot(x, ys, colors=[COLORS[c] for c in CATS], edgecolor="white", linewidth=1.6, alpha=1.0)
    ax.vlines(x, 0, 100, color="white", linewidth=0.8, alpha=0.55, zorder=3)
    cum = np.cumsum(ys, axis=0)
    mid = lambda ci, xi: (cum[ci - 1][xi] if ci else 0) + ys[ci][xi] / 2

    def lab(ci, xi, dy=0):
        c = CATS[ci]
        ax.text(xi, mid(ci, xi) + dy, f"{ys[ci][xi]:.1f}%", ha="center", va="center", fontsize=12.5, fontweight="bold", color=TEXT_ON[c], zorder=5)

    marks = {2: [0, 1, 2], 4: [0, 1, 2, 3], 5: [1]}  # 변곡점 시기에 수치 라벨
    for xi, cis in marks.items():
        for ci in cis:
            lab(ci, xi)
    # 변곡점 안내(영역 위쪽)
    for xi, txt in ((2, "종교·상업\n확장"), (4, "종교·상업\n확장"), (5, "가정·사교\n회귀")):
        ax.text(xi, 101.5, f"▼ {txt}", ha="center", va="bottom", fontsize=11.5, linespacing=1.15, fontweight="bold", color=BURGUNDY if xi != 5 else COLORS["가정·사교·공동체"])
    ax.set_xticks(x, xlabels(p))
    ax.set_xlim(-0.25, len(p) - 0.75)
    ax.set_ylim(0, 100)
    ax.set_yticks(range(0, 101, 20), [f"{t}%" for t in range(0, 101, 20)])
    base(ax)
    ax.grid(False)
    legend_below(ax, y=-0.2)
    ax.set_title("시기별 4대 범주 비중: 한 방향이 아니라 오르내림", loc="left", fontsize=17, fontweight="bold", pad=74)
    ax.text(0, 1.155, "각 시기 표본값을 선으로 이은 것(시기 사이는 연결선) · 시기당 5개 지면 표본이라 일부 변동은 지면 차이일 수 있음", transform=ax.transAxes, fontsize=11, color=MUTED, va="bottom")
    return fig


def c13_heat(d):
    """13쪽: 히트맵 — 시기 × 7개 세부유형 비중(%)."""
    s = d["sub"].copy()
    pct = s[[f"pct_{x}" for x in SUBTYPE_ORDER]].values
    cnt = s[[f"n_{x}" for x in SUBTYPE_ORDER]].values
    cmap = LinearSegmentedColormap.from_list("vintage", ["#F7F1E6", "#D9B8A0", BURGUNDY])
    fig, ax = new((FIG_W + 0.6, FIG_H + 0.6))
    ax.imshow(pct, cmap=cmap, norm=PowerNorm(0.55, vmin=0, vmax=82), aspect="auto")
    for i in range(pct.shape[0]):
        for j in range(pct.shape[1]):
            v, n = pct[i, j], cnt[i, j]
            col = "white" if v >= 38 else INK
            if n == 0:
                ax.text(j, i, "–", ha="center", va="center", fontsize=13, color=MUTED)
            else:
                ax.text(j, i - 0.12, f"{v:.1f}%", ha="center", va="center", fontsize=13, fontweight="bold", color=col)
                ax.text(j, i + 0.22, f"n={n}", ha="center", va="center", fontsize=9.5, color=col if v >= 38 else MUTED)
    ax.set_xticks(np.arange(-0.5, 7, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 7, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2.5)
    ax.grid(which="major", visible=False)
    ax.tick_params(which="both", length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xticks(range(7), [x.replace("·", "·\n", 1) if len(x) > 6 else x for x in SUBTYPE_ORDER], fontsize=11.5)
    ax.xaxis.tick_top()
    ax.tick_params(axis="x", pad=14)
    ax.set_yticks(range(7), [f"{r.period} (4 yrs, n={r.n})" if r.period == "1960–63" else f"{r.period} (n={r.n})" for r in s.itertuples()], fontsize=12)
    # 세부유형이 속한 4대 범주를 맨 위 색 띠로 표시
    for j, x in enumerate(SUBTYPE_ORDER):
        ax.add_patch(Rectangle((j - 0.5 + 0.04, -0.5 - 0.14), 0.92, 0.1, color=COLORS[SUBTYPE_CAT[x]], clip_on=False, transform=ax.transData))
    # 눈여겨볼 칸을 금색 테두리로 표시: 1940s 시사·단신, 상업화 비판·성찰형이 나온 시기
    hi = [(s.index[s.period == "1940s"][0], SUBTYPE_ORDER.index("시사·단신"))]
    jc = SUBTYPE_ORDER.index("상업화 비판·성찰형")
    hi += [(i, jc) for i in range(7) if cnt[i, jc] > 0]
    for i, j in hi:
        ax.add_patch(Rectangle((j - 0.5 + 0.06, i - 0.5 + 0.06), 0.88, 0.88, fill=False, edgecolor=GOLD_MUTED, linewidth=3.2, zorder=6))
    handles = cat_handles()
    ax.legend(handles, CATS, loc="upper center", bbox_to_anchor=(0.5, -0.03), ncol=4, frameon=False, fontsize=11.5, handlelength=1.2, columnspacing=1.6, title="위쪽 색 띠 = 세부유형이 속한 4대 범주", title_fontsize=10.5)
    fig.text(0.01, 0.995, "시기 × 세부유형 비중: 1940s에 시사·단신이 늘고 상업화 비판은 1920s에 처음 두드러짐", fontsize=16.5, fontweight="bold", ha="left", va="top")
    fig.text(0.01, 0.945, "금색 테두리: 1940s 시사·단신(14.8%)과 상업화 비판·성찰형이 나온 시기 · 칸 안 % = 그 시기 조각 중 비중, n = 건수 · 작은 값도 보이도록 색을 보정", fontsize=10.8, color=MUTED, ha="left", va="top")
    fig.tight_layout(rect=[0, 0.02, 1, 0.9])
    return fig


def c13_trend(d):
    """핵심 두 표현의 시기별 4대 범주 비율. 제목·부제 간격을 충분히 벌려 겹치지 않게 한다."""
    p = d["period"]
    periods = p.period.tolist()
    inst = d["inst"]
    fig, axes = plt.subplots(1, 2, figsize=(FIG_W + 2.4, FIG_H + 0.6), sharey=True)
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
    fig.tight_layout(rect=[0, 0.07, 1, 0.80])  # 상단 20%를 제목·부제 자리로 비워 둠(top=0.80)
    fig.text(0.01, 0.96, "핵심 두 표현의 시기별 4대 범주 비율", fontsize=17, fontweight="bold", ha="left", va="top")
    fig.text(0.01, 0.90, "막대 위 n: 해당 시기에 그 표현이 나온 조각 수 · 흐린 막대는 n이 5 미만이라 비율 해석에 주의", fontsize=11.5, color=MUTED, ha="left", va="top")
    return fig


def c16(d):
    """16쪽: 시기별 저신뢰 비중(선+영역)과 검증 지표 요약."""
    c = d["conf"]
    avg = float(d["overall"].query("section == 'confidence' and item == 'low'").iloc[0].pct)
    n_low_all = int(d["overall"].query("section == 'confidence' and item == 'low'").iloc[0].n)
    v1 = d["versions"].query("version == 'v0.1' and source == '검증 실행(45건)'").iloc[0]
    rp = d["repro"].query("metric == 'category'").iloc[0]
    x = np.arange(len(c))
    fig = plt.figure(figsize=(FIG_W + 2.4, FIG_H + 0.4))
    gs = fig.add_gridspec(1, 2, width_ratios=[3.1, 1], wspace=0.08)
    ax = fig.add_subplot(gs[0])
    ax.fill_between(x, 0, c.pct_low, color=BURGUNDY, alpha=0.16, zorder=1)
    ax.plot(x, c.pct_low, color=BURGUNDY, linewidth=2.8, zorder=3)
    peak = c.pct_low > avg * 1.5
    ax.scatter(x[~peak], c.pct_low[~peak], s=90, color="white", edgecolor=BURGUNDY, linewidth=2.2, zorder=4)
    ax.scatter(x[peak], c.pct_low[peak], s=210, color=BURGUNDY, edgecolor="white", linewidth=2, zorder=4)
    for xi, r in zip(x, c.itertuples()):
        pk = bool(peak.iloc[xi])
        ax.text(xi, r.pct_low + (2.0 if pk else 1.5), f"{r.pct_low:.1f}%" + (f"\n({int(r.n_low)}건)" if pk else ""), ha="center", va="bottom", fontsize=14 if pk else 11.5,
                fontweight="bold" if pk else "normal", color=BURGUNDY if pk else MUTED, zorder=5, bbox=label_box())
    ax.axhline(avg, color=INK, linestyle=(0, (4, 3)), linewidth=1.5, zorder=2)
    ax.text(-0.25, avg + 0.5, f"전체 평균 {avg:.1f}%", ha="left", va="bottom", fontsize=11.5, color=INK)
    ax.set_xticks(x, xlabels(c))
    ax.set_xlim(-0.3, len(c) - 0.5)
    ax.set_ylim(0, c.pct_low.max() * 1.35)
    ax.set_yticks(range(0, 31, 10), [f"{t}%" for t in range(0, 31, 10)])
    ax.set_ylabel("AI 확신이 낮은(low) 조각 비중")
    base(ax)
    ax.set_title("AI 확신이 낮은 조각은 1920s·1940s에 몰림", loc="left", fontsize=17, fontweight="bold", pad=26)
    ax.text(0, 1.03, "시기별 low 신뢰도 비중 · 이 시기들은 맥락이 섞여 분류가 어려운 조각이 많았다는 단서(원문 점검 필요)", transform=ax.transAxes, fontsize=11, color=MUTED, va="bottom")
    # 오른쪽: 검증 지표 요약
    tx = fig.add_subplot(gs[1])
    tx.axis("off")
    tx.set_xlim(0, 1)
    tx.set_ylim(0, 1)
    items = [
        (f"{float(v1.category_accuracy_pct):.1f}%", f"범주 정확도 (공식 기준선 v0.1)\n연구자 정답 45건 · κ={float(v1.cohen_kappa):.3f}"),
        (f"{float(rp.agreement_pct):.1f}%", f"재실행 일치율\n같은 45건 중 {int(rp.n_match)}건 일치"),
        (f"{avg:.1f}%", f"low 신뢰도 조각\n전체 788건 중 {n_low_all}건"),
    ]
    for k, (big, small) in enumerate(items):
        y0 = 0.93 - k * 0.32
        tx.plot([0.02, 0.98], [y0 + 0.02, y0 + 0.02], color=AXIS, linewidth=1)
        tx.text(0.03, y0 - 0.02, big, fontsize=26, fontweight="bold", color=BURGUNDY, va="top")
        tx.text(0.03, y0 - 0.115, small, fontsize=10.8, color=MUTED, va="top", linespacing=1.4)
    return fig


def c18(d):
    """18쪽(기존 유지): 극단 지면 제외 후 종교·기원 비율 선 비교."""
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


CHARTS = [c05, c08, c09, c10, c12, c13_heat, c13_trend, c16, c18]


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
    print(f"입력 점검 통과(시기 7개·788건·범주 합 100%·세부유형 대응·혼동행렬 정확도·상위 표현 건수 일치). 한글 폰트: {font}")
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
