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
# 1b. 연간 거래량 vs 가격 지수(2006=100)
# ============================================================
y = pd.read_csv("../output/01_yearly_yoy.csv")
y["volume_idx"] = 100 * (y["n_trades"] / y["n_trades"].iloc[0])
y["price_idx"] = 100 * (y["median_price_per_m2"] / y["median_price_per_m2"].iloc[0])

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(y["deal_year"], y["volume_idx"], color=TEAL, linewidth=2.4, marker="o", markersize=4, label="거래량 지수", zorder=3)
ax.plot(y["deal_year"], y["price_idx"], color=NAVY, linewidth=2.4, marker="o", markersize=4, label="단가(㎡당) 지수", zorder=3)
ax.axhline(100, color="#C3C2B7", linewidth=1, linestyle=":", zorder=1)
style_ax(ax, "연간 거래량 지수 vs 단가 지수 (2006년=100)", "연도", "지수(2006=100)")
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
order = ["해당없음", "구역지정", "추진위", "조합설립", "사업시행", "관리처분", "착공", "건축심의"]
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
# 4b. 한강 조망 유무 단가 비교
# ============================================================
rv = pd.read_csv("../output/04_river_view_price.csv")
rv.columns = ["has_river_view", "n", "median", "mean"]
rv["label"] = rv["has_river_view"].map({True: "한강 조망 O", False: "한강 조망 X"})

fig, ax = plt.subplots(figsize=(6, 5.5))
ax.bar(rv["label"], rv["median"], color=[GREY, TEAL], zorder=3, width=0.55)
for i, v in enumerate(rv["median"]):
    ax.text(i, v + 20, f"{v:,.0f}만원", ha="center", fontsize=11, color=NAVY, weight="bold")
style_ax(ax, "한강 조망 세대 비율 유무별 ㎡당 단가", "", "㎡당 단가(만원)")
fig.tight_layout()
save(fig, "04b_river_view_price")

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
# 7. 정비사업 강도 vs 가격 변동성 산점도
# ============================================================
ji = pd.read_csv("../output/07_redevelop_intensity_vs_volatility.csv")

fig, ax = plt.subplots(figsize=(8, 6))
ax.scatter(ji["redevelop_intensity"], ji["volatility"], color=TEAL, alpha=0.6, s=28, zorder=3, edgecolor="white", linewidth=0.4)
z = np.polyfit(ji["redevelop_intensity"], ji["volatility"], 1)
xs = np.linspace(ji["redevelop_intensity"].min(), ji["redevelop_intensity"].max(), 50)
ax.plot(xs, np.polyval(z, xs), color=NAVY, linewidth=2, zorder=4)
style_ax(ax, "동별 정비사업 진행 강도 vs 매매지수 변동성 (상관계수 0.21)", "정비사업 진행 세대 비중(재고 대비)", "분기 변화율 표준편차")
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
style_ax(ax, "동 간 반응이 가장 크게 갈린 이벤트 5개 (4분기 뒤 상승한 동 비율)", "상승한 동 비율(%)", "")
fig.tight_layout()
save(fig, "08_low_consensus_events")

# ============================================================
# 9. 클러스터링 한계: 클러스터 크기 쏠림
# ============================================================
cl = pd.read_csv("../output/09_dong_clusters.csv")
sizes = cl["cluster"].value_counts().sort_index()

fig, ax = plt.subplots(figsize=(7, 5))
colors = [RED if s == sizes.max() else GREY for s in sizes]
ax.bar(sizes.index.astype(str), sizes.values, color=colors, zorder=3)
for i, v in enumerate(sizes.values):
    ax.text(i, v + 2, str(v), ha="center", fontsize=10, color=NAVY)
style_ax(ax, "클러스터별 동 개수 — 한 클러스터에 쏠려 해석 불가", "클러스터 번호", "동 개수")
fig.tight_layout()
save(fig, "09_cluster_size_imbalance")

print("\n전체 그림 생성 완료:", OUT_DIR)
