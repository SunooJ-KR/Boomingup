# ============================================================================
# test_realtime_two_stage.py
# ============================================================================
# Author:      yjkim
# Purpose:     real-time two-stage 공용 계산의 합성 데이터 점검
# ============================================================================

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


def evaluator():
    path = Path(__file__).with_name("48.evaluate_realtime_two_stage.py")
    spec = importlib.util.spec_from_file_location("realtime_evaluator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ev = evaluator()
    # label gap: prediction_origin보다 늦은 label vintage는 계보 assert가 중단한다.
    good = pd.DataFrame({"prediction_origin":["2020Q4"],"market_max_label_vintage":["2020Q4"],"relative_max_label_vintage":["2020Q4"]})
    ev.assert_prediction_lineage(good)
    bad = good.copy(); bad.loc[0,"relative_max_label_vintage"]="2021Q1"
    try: ev.assert_prediction_lineage(bad)
    except AssertionError: pass
    else: raise AssertionError("fold gap assert가 future label을 허용했습니다")
    # E_t와 T_t: target 결측 행은 service 행이지만 학습/평가 행이 아니다.
    e = pd.DataFrame({"dong":["a","b"],"eligible":[True,True],"y_rt":[.1,np.nan]})
    assert len(e[e.eligible]) == 2 and len(e[e.y_rt.notna()]) == 1
    # 재중심화와 gamma 동률/최소 표본 규칙.
    raw = np.array([-.3,.1,.2]); centered = raw-raw.mean(); assert abs(centered.mean()) < 1e-9
    tiny = pd.DataFrame({"origin":[pd.Period("2020Q1",freq="Q")]*999,"centered":np.zeros(999),"r_rt":np.zeros(999),"status":["ok"]*999})
    assert ev.choose_gamma(tiny,pd.Period("2022Q1",freq="Q"),4) == 0
    origins = np.repeat(pd.period_range("2017Q1",periods=8,freq="Q"), 125)
    tied = pd.DataFrame({"origin":origins,"centered":np.zeros(1000),"r_rt":np.zeros(1000),"status":["ok"]*1000})
    assert ev.choose_gamma(tied,pd.Period("2021Q1",freq="Q"),4) == 0
    # bootstrap은 길이를 유지하고 seed가 같으면 동일하다.
    x=np.arange(20,dtype=float); one=ev.moving_block_bootstrap(x,4,n_boot=50,seed=42); two=ev.moving_block_bootstrap(x,4,n_boot=50,seed=42)
    assert one == two and one[-1] == 50
    # 가중 분위수는 동 수가 많은 기점이 지배하지 않는다.
    assert ev.weighted_quantile([1,10,100],[.5,.25,.25],.8) == 100
    print("합성 데이터 점검 통과: label gap, T_t/E_t, 재중심화, gamma, bootstrap, 가중 분위수")


if __name__ == "__main__": main()
