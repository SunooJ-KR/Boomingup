# ============================================================================
# 65.build_nowcast.py
# ============================================================================
# Author:      yjkim
# Purpose:     잠정 분기 지수의 편향을 재고 보정식을 학습한다 (Track N 후보 N-3)
# Description: 잠정 지수 보정 실험. 채택 여부는 docs/decisions.md 결정 49·50.
#
#              문제: 분기가 끝난 직후의 지수는 아직 신고되지 않은 거래가 빠져 있어
#              확정 지수와 다르다. 화면 헤드라인이 이 잠정 지수라 보정이 필요하다.
#
#              **가정 — 반드시 읽을 것.** 원장에 신고일이 없고 과거 vintage도 없어서
#              "그때 무엇이 보였는지"를 직접 알 수 없다. 그래서 두 단계로 나눈다.
#                (1) 학습은 가정 없이 한다. 분기 안에서 계약일이 늦은 거래를 잘라내고
#                    "먼저 계약된 것만 볼 때 지수가 얼마나 치우치는가"를 잰다. 계약일은
#                    관측값이므로 이 편향은 실재하는 양이다
#                (2) 배포할 때만 "신고는 계약 후 30일"이라는 가정으로 경과일수를
#                    (1)의 관측 비율로 옮긴다. 이 가정은 snapshot이 4분기 쌓이면
#                    실측 도착 곡선(N-1)으로 갈아끼운다
#              따라서 아래 수치는 신고 지연 자체가 아니라 **분기 안 계약 시점 구성에서
#              오는 편향**을 잰 것이다. 문서에 그대로 옮길 것.
#
#              비용을 줄인 방법: 단지×면적bin 고정효과는 전체 표본으로 한 번만 추정하고,
#              부분 표본에서는 구×분기와 동×분기 효과만 다시 계산한다. 잘라낸 쪽과
#              전체 쪽이 같은 고정효과를 쓰므로 둘의 차이는 표본 구성에서만 온다.
# ============================================================================

# ============================================================================
# 0. 환경 설정
# ============================================================================

from pathlib import Path

import numpy as np
import pandas as pd

from _dong_index import RIDGE_LAMBDA, estimate_hedonic_index, load_sales_any

work_dir = Path(__file__).resolve().parents[2]
output_dir = work_dir / "output"

LAST_COMPLETE_QUARTER = pd.Period("2026Q2", freq="Q")
FIRST_EVAL_QUARTER = pd.Period("2011Q1", freq="Q")   # 이전 구간은 거래가 적어 분기 안 절단이 불안정하다
REPORT_LAG_DAYS = 30                                  # 배포 단계에서만 쓰는 가정 (§Description)
# 분기 안에서 "며칠까지 계약된 것만 보이는가". 분기 종료 후 경과일수로 옮기면
# 0일=62일차, 15일=77일차에 해당한다(30일 신고 가정)
VISIBLE_DAYS = [31, 46, 62, 77, 92]
BOOTSTRAP_ROUNDS = 2000
BOOTSTRAP_SEED = 20260917


# ============================================================================
# 1. 매매와 전체 표본 고정효과
# ============================================================================

sales, source = load_sales_any(work_dir)
sales = sales[(sales["quarter"] <= LAST_COMPLETE_QUARTER) & sales["deal_date"].notna()].reset_index(drop=True)
print("===== 1. 매매 적재 =====")
print(f"  원천: {source} / {len(sales):,}건")

_, diagnostics, components = estimate_hedonic_index(sales, ridge_lambda=RIDGE_LAMBDA, with_components=True)
cell_effect = components["cell_effect"]
sales["residual"] = sales["log_ppm2"] - sales["cell"].map(cell_effect).to_numpy()
sales["day_in_quarter"] = (sales["deal_date"] - sales["quarter"].dt.start_time).dt.days + 1
print(f"  단지 고정효과 {len(cell_effect):,}개, 잔차 SD {diagnostics['residual_sd']:.4f}")


# ============================================================================
# 2. 부분 표본 지수 (구×분기 + 동×분기만 다시 계산)
# ============================================================================

def quarter_index(frame):
    """잔차에서 구 수준과 동 편차를 구해 동 지수를 만든다. 전체 추정식과 같은 구조다."""
    gu_level = frame.groupby("sggCd")["residual"].mean()
    centered = frame["residual"] - frame["sggCd"].map(gu_level)
    by_dong = centered.groupby(frame["dong"]).agg(["sum", "size"])
    # ridge 수축: 편차 = 잔차합 / (건수 + λ). 거래가 적은 동은 구 수준 쪽으로 눌린다
    deviation = by_dong["sum"] / (by_dong["size"] + RIDGE_LAMBDA)
    gu_by_dong = frame.drop_duplicates("dong").set_index("dong")["sggCd"].map(gu_level)
    return (gu_by_dong + deviation).rename("log_index"), by_dong["size"].rename("n_sales")


records = []
quarters = pd.period_range(FIRST_EVAL_QUARTER, LAST_COMPLETE_QUARTER, freq="Q")
for quarter in quarters:
    block = sales[sales["quarter"] == quarter]
    if block.empty:
        continue
    final_index, final_n = quarter_index(block)

    for visible_days in VISIBLE_DAYS:
        partial = block[block["day_in_quarter"] <= visible_days]
        if partial.empty:
            continue
        partial_index, partial_n = quarter_index(partial)

        frame = pd.concat([final_index.rename("final"), partial_index.rename("provisional"),
                           final_n.rename("n_final"), partial_n.rename("n_partial")], axis=1)
        frame = frame[frame["n_partial"].notna() & frame["final"].notna()].reset_index()
        frame["revision"] = frame["final"] - frame["provisional"]
        frame["quarter"] = quarter
        frame["visible_days"] = visible_days
        # 편향이 생기는 통로: 분기 안에서 값이 오르는 중이면 늦게 계약된 거래가 더 비싸다.
        # 보이는 부분의 기울기(하루당 log 변화)는 관측 시점에 계산할 수 있다
        if len(partial) >= 30:
            slope = np.polyfit(partial["day_in_quarter"], partial["residual"], 1)[0]
        else:
            slope = 0.0
        frame["visible_slope"] = slope
        records.append(frame)

panel = pd.concat(records, ignore_index=True)
panel["observed_share"] = panel["n_partial"] / panel["n_final"]
# 92일치는 잘라낸 것이 없어 수정폭이 정의상 0이다. 학습에 넣으면 보정식이 0을 맞히는
# 쪽으로 끌려가 정작 보정이 필요한 구간을 놓친다
panel = panel[panel["visible_days"] < 92].reset_index(drop=True)
print("\n===== 2. 잠정-확정 패널 =====")
print(f"  {len(panel):,}행 = 동×분기×관측시점, 분기 {panel['quarter'].nunique()}개")


# ============================================================================
# 3. 보정식 — 관측 시점에 알 수 있는 값만 쓴다
# ============================================================================

# n_final과 observed_share는 확정된 뒤에야 알 수 있으므로 feature로 쓸 수 없다.
# 관측 시점에 아는 것은 지금까지 본 건수, 그 동의 평소 거래량, 며칠치를 봤는지다
panel["typical_n"] = panel.groupby("dong")["n_final"].transform(
    lambda counts: counts.shift().rolling(8, min_periods=2).mean())
panel = panel[panel["typical_n"].notna()].reset_index(drop=True)

panel["log_n_ratio"] = np.log((panel["n_partial"] + 1) / (panel["typical_n"] + 1))
panel["visible_share"] = panel["visible_days"] / 92
panel["log_n_partial"] = np.log1p(panel["n_partial"])

# 남은 일수 × 기울기가 "아직 안 본 구간에서 값이 얼마나 더 움직였을까"에 해당한다
panel["slope_x_remaining"] = panel["visible_slope"] * (92 - panel["visible_days"])
FEATURES = ["log_n_ratio", "visible_share", "log_n_partial", "visible_slope", "slope_x_remaining"]
design = np.column_stack([np.ones(len(panel))] + [panel[name].to_numpy() for name in FEATURES])
target = panel["revision"].to_numpy()

# 같은 자료로 적합하고 평가하면 계수 6개가 62개 분기를 외운 것을 성능으로 읽게 된다.
# 기점 q의 보정식은 q보다 앞선 분기만으로 만든다(결정 41의 embargo 규칙과 같은 원칙).
# 기점 q의 수정폭은 q가 확정된 뒤에야 알 수 있으므로 학습 표본은 q 이전 분기다
quarter_values = panel["quarter"].to_numpy()
ordered_quarters = np.array(sorted(panel["quarter"].unique()))
MIN_TRAIN_QUARTERS = 8

panel["correction"] = np.nan
for position, quarter in enumerate(ordered_quarters):
    if position < MIN_TRAIN_QUARTERS:
        continue
    train = quarter_values < quarter
    test = quarter_values == quarter
    fitted, *_ = np.linalg.lstsq(design[train], target[train], rcond=None)
    panel.loc[test, "correction"] = design[test] @ fitted

evaluated = panel[panel["correction"].notna()].reset_index(drop=True)
in_sample, *_ = np.linalg.lstsq(design, target, rcond=None)

print("\n===== 3. 보정식 계수 (전체 표본 적합, 참고용) =====")
for name, value in zip(["상수"] + FEATURES, in_sample):
    print(f"  {name:>16s} {value:+.5f}")
print(f"  평가는 기점 이전 분기만으로 적합한 값으로 한다 "
      f"(최소 학습 {MIN_TRAIN_QUARTERS}개 분기, 평가 기점 {evaluated['quarter'].nunique()}개)")
panel = evaluated


# ============================================================================
# 4. 무보정 대비 개선 — 분기 블록 bootstrap
# ============================================================================

panel["abs_raw"] = panel["revision"].abs()
panel["abs_corrected"] = (panel["revision"] - panel["correction"]).abs()

by_quarter = panel.groupby("quarter")[["abs_raw", "abs_corrected"]].mean()
raw_mae, corrected_mae = by_quarter["abs_raw"].mean(), by_quarter["abs_corrected"].mean()

# 같은 분기 안의 동들은 시장 공통 오차를 나눠 갖는다. 동 단위로 재표본하면 표본수를
# 부풀리게 되므로 분기 단위로 뽑는다
rng = np.random.default_rng(BOOTSTRAP_SEED)
quarter_list = by_quarter.index.to_numpy()
draws = rng.integers(0, len(quarter_list), size=(BOOTSTRAP_ROUNDS, len(quarter_list)))
gains = [by_quarter["abs_raw"].to_numpy()[draw].mean() - by_quarter["abs_corrected"].to_numpy()[draw].mean()
         for draw in draws]
low, high = np.percentile(gains, [2.5, 97.5])

print("\n===== 4. 수정폭 MAE (기점 동일 가중) =====")
print(f"  무보정 {raw_mae:.5f} → 보정 {corrected_mae:.5f} ({corrected_mae / raw_mae - 1:+.1%})")
print(f"  개선폭 {raw_mae - corrected_mae:+.5f}, 분기 블록 bootstrap 95% 구간 [{low:+.5f}, {high:+.5f}]")
passed = low > 0
print(f"  판정: 구간이 0을 {'제외한다 — N-3 채택 조건 충족' if passed else '포함한다 — 채택 조건 미충족'}")

print("\n  관측 시점별 (동 평균):")
by_days = panel.groupby("visible_days").agg(
    관측비율=("observed_share", "mean"), 무보정=("abs_raw", "mean"), 보정=("abs_corrected", "mean"))
by_days["분기종료후_경과일_가정"] = [days - 92 + REPORT_LAG_DAYS for days in by_days.index]
print(by_days.to_string(float_format=lambda value: f"{value:.4f}"))


# ============================================================================
# 5. 저장
# ============================================================================

panel_path = output_dir / "65.1.nowcast_panel.txt"
panel.to_csv(panel_path, sep="\t", index=False, lineterminator="\n")
model_path = output_dir / "65.2.nowcast_model.txt"
pd.DataFrame({"term": ["intercept"] + FEATURES, "coefficient": in_sample}).to_csv(
    model_path, sep="\t", index=False, lineterminator="\n")

print(f"\n패널: {panel_path}")
print(f"보정식: {model_path}")
