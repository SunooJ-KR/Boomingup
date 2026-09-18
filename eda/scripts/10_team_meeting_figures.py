"""팀 미팅 발표자료용 그림 생성. 축 1~9에서 이미 저장한 eda/output/*.csv를
다시 읽어서 그린다(새로 DB를 조회하지 않음 — 산출물 재사용 원칙).

산출물: eda/output/10.team_meeting_figures/*.png
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
fm.fontManager.addfont(FONT_PATH)
plt.rcParams["font.family"] = "Noto Sans CJK KR"
plt.rcParams["axes.unicode_minus"] = False

# 발표자료(slide_deck.py) 색상과 통일
NAVY = "#002632"
TEAL = "#40CDDC"
AMBER = "#B1760A"
GREY = "#5B6B70"
RED = "#C0392B"
GREEN = "#1E7A3C"
LIGHT = "#F3F6F6"

OUT_DIR = "../output/10.team_meeting_figures"
os.makedirs(OUT_DIR, exist_ok=True)


def style_ax(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=13, color=NAVY, weight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=10, color=GREY)
    ax.set_ylabel(ylabel, fontsize=10, color=GREY)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#C3C2B7")
    ax.spines["bottom"].set_color("#C3C2B7")
    ax.tick_params(colors=GREY, labelsize=9)
    ax.grid(axis="y", color="#E1E0D9", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def save(fig, name):
    path = f"{OUT_DIR}/{name}.png"
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved", path)


# ============================================================
# 1a. 분기별 거래량 + 규제 이벤트 시점
# ============================================================
q = pd.read_csv("../output/01_quarterly_trend.csv")
events = pd.read_csv("../output/01_market_events.csv")
events["effective_date"] = pd.to_datetime(events["effective_date"])
events = events[events["category"] == "policy"]

fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(range(len(q)), q["n_trades"], color=TEAL, width=0.75, zorder=3)
xticks = list(range(0, len(q), 4))
ax.set_xticks(xticks)
ax.set_xticklabels(q["quarter"].iloc[xticks], rotation=45, ha="right")
style_ax(ax, "분기별 매매 거래량과 정책 이벤트 시점", "분기", "거래 건수")

# 이벤트를 분기 위치로 변환해 세로선 표시(policy tighten/ease만, 너무 많으면 가독성 저하되므로 상위만)
q_quarter_pos = {row["quarter"]: i for i, row in q.iterrows()}
events["quarter"] = events["effective_date"].dt.year.astype(str) + "Q" + ((events["effective_date"].dt.month - 1) // 3 + 1).astype(str)
key_events = events[events["quarter"].isin(["2017Q3", "2023Q1"])].drop_duplicates("quarter")
for _, ev in key_events.iterrows():
    if ev["quarter"] in q_quarter_pos:
        x = q_quarter_pos[ev["quarter"]]
        color = RED if ev["direction"] == "tighten" else GREEN
        ax.axvline(x, color=color, linestyle="--", linewidth=1.3, zorder=2)
        ax.annotate(("규제강화" if ev["direction"] == "tighten" else "규제완화") + f"\n{ev['quarter']}",
                     xy=(x, ax.get_ylim()[1] * 0.92), fontsize=9, color=color, ha="center")

fig.tight_layout()
save(fig, "01a_quarterly_volume_events")

# ============================================================
# 1b. 연간 거래량 vs 가격 지수(2006~2008 평균=100)
# ============================================================
y = pd.read_csv("../output/01_yearly_yoy.csv")
# 단일 연도(2006년)를 기준점으로 쓰면 왜곡된다 — 2006년은 21개 연도 중 거래량 2위(111,946건,
# 2007~2013년 평균의 2배 이상)이면서 동시에 단가는 전체 최저치(342만원/㎡)인 이상치에 가까운
# 해였다(2026-09-16 확인). 그 해 하나를 100으로 놓으면 이후 가격 상승·거래량 감소가 모두
# 과장돼 보인다. 초반 3개년(2006~2008) 평균을 기준으로 삼아 단일 연도의 튐을 줄인다.
base_years = y[y["deal_year"].between(2006, 2008)]
volume_base = base_years["n_trades"].mean()
price_base = base_years["median_price_per_m2"].mean()
y["volume_idx"] = 100 * (y["n_trades"] / volume_base)
y["price_idx"] = 100 * (y["median_price_per_m2"] / price_base)
# 마지막 연도(2026)는 8월까지만 있는 불완전 연도라 실선으로 이어그리면 "급락"처럼 보일 위험이
# 있다(2026-09-16 codex 검증 지적) — 마지막 구간만 점선+빈 마커로 구분한다.
is_complete = y["is_complete_year"].astype(bool)
last_complete_idx = is_complete.sum() - 1  # 마지막 완결 연도 행 위치

fig, ax = plt.subplots(figsize=(10, 5))
for col, color, label in [("volume_idx", TEAL, "거래량 지수"), ("price_idx", NAVY, "단가(㎡당) 지수")]:
    ax.plot(y["deal_year"][:last_complete_idx + 1], y[col][:last_complete_idx + 1],
            color=color, linewidth=2.4, marker="o", markersize=4, label=label, zorder=3)
    ax.plot(y["deal_year"][last_complete_idx:], y[col][last_complete_idx:],
            color=color, linewidth=2.4, linestyle="--", marker="o", markersize=4,
            markerfacecolor="white", zorder=3)
ax.axhline(100, color="#C3C2B7", linewidth=1, linestyle=":", zorder=1)
last_year = y["deal_year"].iloc[-1]
ax.annotate(f"{last_year}년은 8월까지만 집계\n(점선 = 불완전 연도)",
            xy=(y["deal_year"].iloc[-1], y["price_idx"].iloc[-1]), xytext=(-95, 15),
            textcoords="offset points", fontsize=8.5, color=GREY,
            arrowprops=dict(arrowstyle="->", color=GREY, lw=1))
style_ax(ax, "연간 거래량 지수 vs 단가 지수 (2006~2008년 평균=100)", "연도", "지수(2006~2008년 평균=100)")
ax.legend(frameon=False, fontsize=10, loc="upper left")
fig.tight_layout()
save(fig, "01b_volume_vs_price_index")

# ============================================================
# 2a. 자치구별 2026년 ㎡당 단가
# ============================================================
gu = pd.read_csv("../output/02_gu_yearly_price.csv")
gu_2026 = gu[["gu", "2026", "gangnam3"]].dropna(subset=["2026"]).sort_values("2026", ascending=True)
colors = [AMBER if g else TEAL for g in gu_2026["gangnam3"]]

fig, ax = plt.subplots(figsize=(8, 9))
ax.barh(gu_2026["gu"], gu_2026["2026"], color=colors, zorder=3)
style_ax(ax, "자치구별 ㎡당 단가 (2026년 중앙값)", "㎡당 단가(만원)", "")
ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=AMBER, label="강남3구"),
                    plt.Rectangle((0, 0), 1, 1, color=TEAL, label="그 외")],
          frameon=False, fontsize=10, loc="lower right")
fig.tight_layout()
save(fig, "02a_gu_price_2026")

# ============================================================
# 2b. 동별 1년 상승률 상위/하위
# ============================================================
d = pd.read_csv("../output/02_dong_yoy_ranked.csv")
top = d.nlargest(8, "yoy_change_pct")
bot = d.nsmallest(8, "yoy_change_pct")
combo = pd.concat([top, bot]).sort_values("yoy_change_pct")
combo["label"] = combo["dong"].str.split("_").str[1] + "(" + combo["gu_name"] + ")"
colors = [GREEN if v > 0 else RED for v in combo["yoy_change_pct"]]

fig, ax = plt.subplots(figsize=(9, 7))
ax.barh(combo["label"], combo["yoy_change_pct"], color=colors, zorder=3)
ax.axvline(0, color=NAVY, linewidth=1)
style_ax(ax, "동별 1년 상승률 상위·하위 8개 (2025Q2→2026Q2, hedonic 지수)", "1년 변화(%)", "")
fig.tight_layout()
save(fig, "02b_dong_yoy_top_bottom")

# ============================================================
# 3a. 준공연차 구간별 단가 (U자형)
# ============================================================
age = pd.read_csv("../output/03_age_price.csv")
age.columns = ["age_bin", "n", "median", "mean"]

fig, ax = plt.subplots(figsize=(9, 5))
ax.bar(age["age_bin"].astype(str), age["median"], color=TEAL, zorder=3)
style_ax(ax, "준공연차 구간별 ㎡당 단가 (2024~2026 거래, 중앙값)", "준공 후 연차(년)", "㎡당 단가(만원)")
ax.set_xticklabels(["0-5", "5-10", "10-20", "20-30", "30-40", "40-60"])
fig.tight_layout()
save(fig, "03a_age_price")

# ============================================================
# 3b. 정비사업 단계별 프리미엄
# ============================================================
stage = pd.read_csv("../output/03_redevelop_stage_price.csv")
# 정비사업 실제 진행 순서: 구역지정 -> 추진위원회 구성 -> 조합설립인가 -> 건축심의 ->
# 사업시행인가 -> 관리처분인가 -> 착공 (뒤로 갈수록 실제 공사에 가까워짐)
order = ["해당없음", "구역지정", "추진위", "조합설립", "건축심의", "사업시행", "관리처분", "착공"]
stage["stage"] = pd.Categorical(stage["stage"], categories=order, ordered=True)
stage = stage.sort_values("stage")

fig, ax = plt.subplots(figsize=(9, 5.5))
colors = [GREY if s == "해당없음" else AMBER for s in stage["stage"]]
ax.bar(stage["stage"].astype(str), stage["premium_vs_none_pct"], color=colors, zorder=3)
style_ax(ax, "정비사업 단계별 단가 프리미엄 (일반 단지=0% 기준)", "정비사업 진행 단계", "프리미엄(%)")
plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
fig.tight_layout()
save(fig, "03b_redevelop_premium")

# ============================================================
# 4a. 역 거리 구간별 단가
# ============================================================
st = pd.read_csv("../output/04_station_dist_price.csv")
st.columns = ["dist_bin", "n", "median"]

fig, ax = plt.subplots(figsize=(9, 5))
ax.bar(st["dist_bin"], st["median"], color=TEAL, zorder=3)
style_ax(ax, "역까지 거리 구간별 ㎡당 단가 (2024~2026 거래, 중앙값)", "가장 가까운 역까지 거리", "㎡당 단가(만원)")
fig.tight_layout()
save(fig, "04a_station_distance_price")

# ============================================================
# 4b. 한강 조망 유무 vs 초등학교 거리 — 입지 요인 두 개를 나란히 비교
# (학군거리는 상관이 거의 없다는 본문 주장의 직접 근거 그림이 빠져있었다 — 2026-09-16 지적)
# ============================================================
rv = pd.read_csv("../output/04_river_view_price.csv")
rv.columns = ["has_river_view", "n", "median", "mean"]
rv["label"] = rv["has_river_view"].map({True: "한강 조망 O", False: "한강 조망 X"})
es = pd.read_csv("../output/04_elem_school_dist_price.csv")
es.columns = ["dist_bin", "n", "median"]

fig, axes = plt.subplots(1, 2, figsize=(12, 5.3), gridspec_kw={"width_ratios": [1, 1.4]})

ax = axes[0]
ax.bar(rv["label"], rv["median"], color=[GREY, TEAL], zorder=3, width=0.55)
for i, v in enumerate(rv["median"]):
    ax.text(i, v + 20, f"{v:,.0f}만원", ha="center", fontsize=11, color=NAVY, weight="bold")
style_ax(ax, "한강 조망 유무별 ㎡당 단가", "", "㎡당 단가(만원)")

ax = axes[1]
bar_colors = [TEAL if n >= 1000 else "#C3C2B7" for n in es["n"]]
ax.bar(es["dist_bin"], es["median"], color=bar_colors, zorder=3)
for i, (n, v) in enumerate(zip(es["n"], es["median"])):
    ax.text(i, v + 20, f"n={n:,}", ha="center", fontsize=8, color=GREY)
style_ax(ax, "초등학교까지 거리별 ㎡당 단가\n(회색=표본 1,000건 미만, 참고용)",
         "가장 가까운 초등학교까지 거리", "㎡당 단가(만원)")

fig.tight_layout()
save(fig, "04b_river_view_vs_school_distance")

# ============================================================
# 5a. 층대별 단가
# ============================================================
fl = pd.read_csv("../output/05_floor_price.csv")
fl.columns = ["floor_bin", "n", "median"]

fig, ax = plt.subplots(figsize=(9, 5))
ax.bar(fl["floor_bin"], fl["median"], color=TEAL, zorder=3)
style_ax(ax, "층대별 ㎡당 단가 (취소 제외 전체 거래, 중앙값)", "층대", "㎡당 단가(만원)")
fig.tight_layout()
save(fig, "05a_floor_price")

# ============================================================
# 5b. 면적대별 단가 (U자형)
# ============================================================
ar = pd.read_csv("../output/05_area_price.csv")
ar.columns = ["area_bin", "n", "median", "mean"]

fig, ax = plt.subplots(figsize=(9, 5))
ax.bar(ar["area_bin"], ar["median"], color=TEAL, zorder=3)
style_ax(ax, "면적대별 ㎡당 단가 (취소 제외 전체 거래, 중앙값)", "전용면적 구간", "㎡당 단가(만원)")
plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
fig.tight_layout()
save(fig, "05b_area_price")

# ============================================================
# 6. 전세가율 5분위별 1년 뒤 매매지수 변화
# ============================================================
je = pd.read_csv("../output/06_jeonse_ratio_vs_future_change.csv")
je.columns = ["jeonse_bin", "n", "median", "mean", "mean_pct"]

fig, ax = plt.subplots(figsize=(8, 5.5))
ax.bar(je["jeonse_bin"], je["mean_pct"], color=TEAL, zorder=3)
style_ax(ax, "기점 전세가율 5분위별 1년 뒤 매매지수 평균 변화", "전세가율 분위(낮음→높음)", "1년 뒤 변화(%, log 기준)")
fig.tight_layout()
save(fig, "06_jeonse_ratio_future_change")

# ============================================================
# 6b. 기점 연도별 전세가율-미래상승률 상관계수 (부호가 해마다 뒤집히는 걸 보여줌)
# ============================================================
yc = pd.read_csv("../output/06_jeonse_correlation_by_year.csv")
colors6b = [GREEN if v > 0 else RED for v in yc["corr"]]

fig, ax = plt.subplots(figsize=(9, 5.5))
ax.bar(yc["origin_year"].astype(int).astype(str), yc["corr"], color=colors6b, zorder=3)
ax.axhline(0, color=NAVY, linewidth=1)
style_ax(ax, "기점 연도별 전세가율-미래상승률 상관계수 (해마다 부호가 뒤집힘)", "기점 연도", "상관계수")
plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
fig.tight_layout()
save(fig, "06b_jeonse_corr_by_year")

# ============================================================
# 7. 정비사업 강도 vs 가격 변동성 산점도
# ============================================================
ji = pd.read_csv("../output/07_redevelop_intensity_vs_volatility.csv")
normal7 = ji[~ji["intensity_over_1"]]
outliers7 = ji[ji["intensity_over_1"]]

fig, ax = plt.subplots(figsize=(8.5, 6.5))
ax.scatter(normal7["redevelop_intensity"], normal7["volatility"], color=TEAL, alpha=0.6, s=28, zorder=3,
           edgecolor="white", linewidth=0.4, label="강도 ≤ 1 (정상 범위)")
ax.scatter(outliers7["redevelop_intensity"], outliers7["volatility"], color=RED, alpha=0.7, s=32, zorder=4,
           edgecolor="white", linewidth=0.4, label="강도 > 1 (재건축 후기 등)")
z = np.polyfit(normal7["redevelop_intensity"], normal7["volatility"], 1)
xs = np.linspace(normal7["redevelop_intensity"].min(), normal7["redevelop_intensity"].max(), 50)
ax.plot(xs, np.polyval(z, xs), color=NAVY, linewidth=2, zorder=5, linestyle="--")
ax.legend(frameon=False, fontsize=9, loc="upper right")
style_ax(ax, "동별 정비사업 진행 강도 vs 매매지수 변동성 — 유의한 관계 없음(강도≤1: r=0.048, p=0.434)",
         "정비사업 진행 세대 비중(전체 세대수 대비)", "분기 변화율 표준편차")
fig.tight_layout()
save(fig, "07_redevelop_intensity_volatility")

# ============================================================
# 8. 컨센서스 낮은 이벤트의 상승 동 비율(50%에 가까울수록 의견 갈림)
# ============================================================
ev8 = pd.read_csv("../output/08_low_consensus_events.csv")
ev8["label_short"] = ev8["label"].str.slice(0, 18) + "\n" + ev8["effective_date"]

fig, ax = plt.subplots(figsize=(9, 5.5))
colors = [RED if s < 0.5 else GREEN for s in ev8["share_up"]]
ax.barh(ev8["label_short"], ev8["share_up"] * 100, color=colors, zorder=3)
ax.axvline(50, color=GREY, linestyle="--", linewidth=1.2)
ax.text(50.5, -0.6, "50% = 정확히 반반", fontsize=8.5, color=GREY)
style_ax(ax, "법정동 간 반응이 가장 크게 갈린 이벤트 5개 (4분기 뒤 상승한 법정동 비율)", "상승한 법정동 비율(%, 자치구 아님)", "")
fig.tight_layout()
save(fig, "08_low_consensus_events")

# ============================================================
# 9. 클러스터링 v2: 시장 공통요인을 뺀 뒤 클러스터별 상대적 움직임
# ============================================================
cl = pd.read_csv("../output/09_dong_clusters.csv")
path = pd.read_csv("../output/09_cluster_avg_path.csv", index_col=0).tail(8)
sizes = cl["cluster"].value_counts().sort_index()

fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": [1, 1.6]})

ax = axes[0]
ax.bar(sizes.index.astype(str), sizes.values, color=TEAL, zorder=3)
for i, v in enumerate(sizes.values):
    ax.text(i, v + 1.5, str(v), ha="center", fontsize=9.5, color=NAVY)
style_ax(ax, "클러스터별 동 개수(균형 잡힘)", "클러스터 번호", "동 개수")

ax = axes[1]
palette9 = [NAVY, TEAL, AMBER, RED, GREEN, GREY]
for i, col in enumerate(path.columns):
    ax.plot(range(len(path)), path[col], color=palette9[i % len(palette9)], linewidth=2,
            marker="o", markersize=3.5, label=f"클러스터 {col}", zorder=3)
ax.axhline(0, color="#C3C2B7", linewidth=1, linestyle=":")
ax.set_xticks(range(len(path)))
ax.set_xticklabels(path.index, rotation=45, ha="right", fontsize=8.5)
ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.28))
style_ax(ax, "클러스터별 시장 대비 초과 변화율(최근 8분기)", "분기", "시장 대비 초과 변화율(log)")

fig.tight_layout()
save(fig, "09_cluster_size_imbalance")

# ============================================================
# 10. 인구 변화율 vs 1년 매매가 변화율 산점도
# (이전 버전은 이 그림을 스크립트 밖에서 즉석으로 그려서 재현 코드가 없었다
#  — 2026-09-16 codex 검증에서 지적됨. 이번엔 스크립트에 편입한다.
#  v2: 보광동 하나가 상관을 만드는 이상치라는 걸(6·7번 축과 같은 패턴) 그대로 보여준다)
# ============================================================
pv = pd.read_csv("../output/12_population_vs_price.csv")
corr_sum10 = pd.read_csv("../output/12_population_correlation_summary.csv").iloc[0]
is_bg = pv["dong"] == "11170_보광동"

fig, ax = plt.subplots(figsize=(8.5, 6.5))
ax.scatter(pv.loc[~is_bg, "pop_change_pct"], pv.loc[~is_bg, "yoy_change_pct"], color=TEAL, alpha=0.55,
           s=26, zorder=3, edgecolor="white", linewidth=0.4, label="보광동 제외 230개 동")
bg10 = pv[is_bg]
ax.scatter(bg10["pop_change_pct"], bg10["yoy_change_pct"], color=RED, s=100, zorder=5,
           edgecolor="white", linewidth=0.8, label="보광동")
ax.annotate(
    f"보광동(용산구)\n인구 {bg10['pop_change_pct'].iloc[0]:.1f}%, 가격 {bg10['yoy_change_pct'].iloc[0]:.1f}%",
    xy=(bg10["pop_change_pct"].iloc[0], bg10["yoy_change_pct"].iloc[0]),
    xytext=(15, -8), textcoords="offset points", fontsize=10, color=RED, weight="bold")
z10 = np.polyfit(pv["pop_change_pct"], pv["yoy_change_pct"], 1)
xs10 = np.linspace(pv["pop_change_pct"].min(), pv["pop_change_pct"].max(), 50)
ax.plot(xs10, np.polyval(z10, xs10), color=NAVY, linewidth=2, zorder=4, linestyle="--")
ax.axvline(0, color="#C3C2B7", linewidth=1, linestyle=":")
ax.legend(frameon=False, fontsize=9, loc="upper right")
style_ax(ax, f"동별 인구 변화율 vs 1년 매매가 변화율 — 보광동 제외 시 관계 사라짐"
             f"(전체 r={corr_sum10['pearson_r']:.3f} p={corr_sum10['p_value']:.2f}, "
             f"제외 r={corr_sum10['pearson_r_excl_bogwangdong']:.3f})",
         "인구 변화율(%)", "매매가 변화율(%, hedonic 지수 기준)")
fig.tight_layout()
save(fig, "10_population_vs_price")

# ============================================================
# 13a. 다변량 회귀 표준화 계수 (여러 요인을 동시에 통제한 뒤 각 요인의 조건부 연관성)
# ============================================================
pct13 = pd.read_csv("../output/13_hedonic_regression_pct.csv").set_index("variable")

label_map13 = {
    "floor": "층수\n(+1표준편차≈6.4층)",
    "log_area": "면적(log)\n(+1표준편차≈1.5배)", "station_dist_m": "역까지 거리\n(+1표준편차≈321m)",
    "river_view_ratio": "한강조망 비율\n(+1표준편차≈0.32)", "elem_school_m": "초등학교 거리\n(+1표준편차≈161m)",
    "mid_school_m": "중학교 거리\n(+1표준편차≈248m)", "high_school_m": "고등학교 거리\n(+1표준편차≈356m)",
}
# 준공연차(age)는 제곱항 때문에 시작 연차에 따라 효과 방향이 달라져 막대 하나로 못 담는다
# -> 아래 13b 곡선 그림으로 따로 표현한다.
reg13 = pct13.copy()
reg13["label"] = [label_map13[i] for i in reg13.index]
reg13 = reg13.sort_values("pct_change_per_1sd")
reg13["sig"] = reg13["p_value"] < 0.05

fig, ax = plt.subplots(figsize=(9.5, 6.0))
colors13 = [NAVY if sig else GREY for sig in reg13["sig"]]
ax.errorbar(reg13["pct_change_per_1sd"], reg13["label"],
            xerr=[reg13["pct_change_per_1sd"] - reg13["ci_low_pct"], reg13["ci_high_pct"] - reg13["pct_change_per_1sd"]],
            fmt="none", ecolor=GREY, capsize=3, zorder=2)
ax.scatter(reg13["pct_change_per_1sd"], reg13["label"], color=colors13, s=70, zorder=3)
ax.axvline(0, color="#C3C2B7", linewidth=1, linestyle=":")
style_ax(ax, "다른 요인을 통제한 뒤 각 변수의 조건부 연관성 — 1표준편차 변할 때 단가 변화(%), 95% 신뢰구간\n"
             "(회색=통계적으로 유의하지 않음, p≥0.05)",
         "㎡당 단가 변화(%, exp(계수×표준편차)-1 기준)", "")
fig.tight_layout()
save(fig, "13a_hedonic_regression_coefs")

# ============================================================
# 13b. 준공연차 효과 곡선 (선형항만 보면 왜곡되는 U자형 관계)
# ============================================================
curve13 = pd.read_csv("../output/13_hedonic_regression_age_curve.csv")

fig, ax = plt.subplots(figsize=(8.5, 5.5))
ax.plot(curve13["age"], curve13["pct_vs_age20"], color=NAVY, linewidth=2.2, zorder=3)
ax.axhline(0, color="#C3C2B7", linewidth=1, linestyle=":")
ax.axvline(20, color=GREY, linewidth=1, linestyle=":")
turning_x = curve13.loc[(curve13["pred_log_price_relative"]).idxmin(), "age"]
ax.axvline(turning_x, color=RED, linewidth=1.3, linestyle="--", zorder=2)
ax.annotate(f"변곡점 ≈ {turning_x:.0f}년", xy=(turning_x, curve13["pct_vs_age20"].min()),
            xytext=(8, -18), textcoords="offset points", fontsize=9.5, color=RED, weight="bold")
style_ax(ax, "준공연차 효과(다른 요인 통제 후) — 20년차 대비 상대적 단가 변화(%)",
         "준공연차(년)", "20년차 대비 단가 변화(%)")
fig.tight_layout()
save(fig, "13b_hedonic_age_curve")

# ============================================================
# 14. 동 클러스터 성향 분석 — 가격 수준 vs 최근 모멘텀(시장 대비 초과 상승률)
# ============================================================
prof14 = pd.read_csv("../output/14_cluster_profile_with_rise.csv")

fig, ax = plt.subplots(figsize=(8.5, 6.5))
for i, row in prof14.iterrows():
    c = int(row["cluster"])
    ax.scatter(row["price_per_m2_median"], row["recent_1y_excess_change_pct"],
               s=row["n_dong"] * 9, color=palette9[(c - 1) % len(palette9)],
               alpha=0.85, zorder=3, edgecolor="white", linewidth=1.2)
    ax.annotate(f"클러스터 {c}\n(동 {int(row['n_dong'])}개)",
                xy=(row["price_per_m2_median"], row["recent_1y_excess_change_pct"]),
                xytext=(9, 6), textcoords="offset points", fontsize=9, color=NAVY, weight="bold")
ax.axhline(0, color="#C3C2B7", linewidth=1, linestyle=":")
style_ax(ax, "클러스터별 성향 — 가격 수준 vs 최근 1년 시장 대비 초과 상승률\n(점 크기 = 클러스터에 속한 동 개수)",
         "㎡당 단가 중앙값(만원, 2024년 이후 거래)", "최근 1년 시장 대비 초과 상승률(%)")
fig.tight_layout()
save(fig, "14_cluster_profile_price_vs_momentum")

# ============================================================
# 15. 9번 축 클러스터링 검증 — 상관행렬 히트맵 + 같은/다른 클러스터 상관 비교
# ============================================================
corr_sorted = pd.read_csv("../output/09b_corr_matrix_sorted.csv", index_col=0)
wb = pd.read_csv("../output/09b_within_vs_between_corr.csv")
order_cluster = pd.read_csv("../output/09b_corr_matrix_order.csv", index_col=0)["cluster"].values

fig, axes = plt.subplots(1, 2, figsize=(13, 6.2), gridspec_kw={"width_ratios": [1.3, 1]})

ax = axes[0]
im = ax.imshow(corr_sorted.values, cmap="RdBu_r", vmin=-0.5, vmax=0.5, aspect="auto")
change_points = np.where(np.diff(order_cluster) != 0)[0] + 1
for cp in change_points:
    ax.axhline(cp - 0.5, color=NAVY, linewidth=1)
    ax.axvline(cp - 0.5, color=NAVY, linewidth=1)
ax.set_xticks([]); ax.set_yticks([])
ax.set_title("동 간 상관계수(클러스터 순서 정렬)\n대각선 블록이 진할수록 클러스터링이 유효함", fontsize=12, color=NAVY, weight="bold")
fig.colorbar(im, ax=ax, label="상관계수", fraction=0.046, pad=0.04)

ax = axes[1]
within = wb.loc[wb["group"] == "같은 클러스터", "corr"]
between = wb.loc[wb["group"] == "다른 클러스터", "corr"]
bp = ax.boxplot([within, between], tick_labels=["같은\n클러스터", "다른\n클러스터"], showmeans=True, patch_artist=True)
for patch, color in zip(bp["boxes"], [TEAL, GREY]):
    patch.set_facecolor(color); patch.set_alpha(0.5)
style_ax(ax, "같은 클러스터 동끼리\n상관이 더 높은가", "", "상관계수")

fig.tight_layout()
save(fig, "09f_cluster_validation_heatmap")

# ============================================================
# 16. 9번 축 클러스터링 검증 — k별 실루엣 점수
# ============================================================
sil = pd.read_csv("../output/09b_silhouette_by_k.csv")
fig, ax = plt.subplots(figsize=(8.5, 5.5))
colors_sil = [RED if k == 6 else TEAL for k in sil["k"]]
ax.bar(sil["k"], sil["silhouette"], color=colors_sil, zorder=3)
style_ax(ax, "클러스터 개수(k)별 실루엣 점수 (빨강 = 이번에 쓴 k=6)", "클러스터 개수(k)", "실루엣 점수")
fig.tight_layout()
save(fig, "09g_silhouette_by_k")

# ============================================================
# 17. 클러스터별 동 개별 경로 — 같은 클러스터 동끼리 실제로 비슷하게 움직이는지 눈으로 확인
# (클러스터링에 쓴 지표(분기별 시장 대비 초과 변화율)를 누적합해서, 각 동이 2016Q1 이후
# 시장 대비 얼마나 앞서/뒤처졌는지 경로로 그린다 — 새 지표가 아니라 같은 지표를 보기 좋게
# 누적한 것일 뿐이다)
# ============================================================
paths = pd.read_csv("../output/09b_dong_cum_excess_path.csv")
paths["cum_excess_pct"] = 100 * (np.exp(paths["cum_excess"]) - 1)
quarters_sorted = sorted(paths["quarter"].unique())
q_pos = {q: i for i, q in enumerate(quarters_sorted)}
paths["q_pos"] = paths["quarter"].map(q_pos)

fig, axes = plt.subplots(2, 3, figsize=(14, 8), sharex=True, sharey=True)
for cl, ax in zip(sorted(paths["cluster"].unique()), axes.flat):
    color = palette9[(int(cl) - 1) % len(palette9)]
    sub = paths[paths["cluster"] == cl]
    for dong, g in sub.groupby("dong"):
        g = g.sort_values("q_pos")
        ax.plot(g["q_pos"], g["cum_excess_pct"], color=color, alpha=0.18, linewidth=0.8, zorder=2)
    avg = sub.groupby("q_pos")["cum_excess_pct"].mean()
    ax.plot(avg.index, avg.values, color=NAVY, linewidth=2.4, zorder=4)
    ax.axhline(0, color="#C3C2B7", linewidth=0.9, linestyle=":", zorder=1)
    n_dong_cl = sub["dong"].nunique()
    ax.set_title(f"클러스터 {cl} (동 {n_dong_cl}개)", fontsize=11, color=NAVY, weight="bold")
    ax.tick_params(colors=GREY, labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#C3C2B7")
    ax.spines["bottom"].set_color("#C3C2B7")

tick_idx = list(range(0, len(quarters_sorted), 8))
for ax in axes[-1]:
    ax.set_xticks(tick_idx)
    ax.set_xticklabels([quarters_sorted[i] for i in tick_idx], rotation=45, ha="right", fontsize=8)
fig.suptitle("클러스터별 동 개별 누적 초과 변화율 경로 (얇은 선=개별 동, 굵은 남색 선=클러스터 평균)",
             fontsize=13, fontweight="bold", color=NAVY, y=1.0)
fig.text(0.5, -0.01, "2016Q1 이후 누적, 시장 평균 대비 %", ha="center", fontsize=9.5, color=GREY)
fig.tight_layout()
save(fig, "09h_dong_paths_by_cluster")

print("\n전체 그림 생성 완료:", OUT_DIR)
