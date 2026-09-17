# ============================================================================
# _dong_cluster.py
# ============================================================================
# Author:      yjkim
# Purpose:     구조 클러스터와 판단 보조 산출물이 같은 동 feature 행렬을 사용하게 한다
# Description: 66.build_dong_cluster.py와 69.build_dong_support.py의 공용 변환이다.
#              결측은 같은 자치구 중앙값, 이후 서울 중앙값 순서로 채운다.
# ============================================================================

import numpy as np


# 서울시청, 강남역. 도심·강남 거리는 위치를 한 축으로 줄인 것이다.
CBD = (37.5665, 126.9780)
GANGNAM = (37.4979, 127.0276)

STRUCTURE_COLUMNS = [
    "log_ppm2",
    "jeonse_ratio",
    "log_stock",
    "new_share",
    "lat",
    "lng",
    "dist_cbd",
    "dist_gangnam",
]


def km_distance(lat, lng, point):
    """위경도 두 점의 대략 거리(km). 서울 안에서는 평면 근사로 충분하다."""
    return np.sqrt(((lat - point[0]) * 111.0) ** 2 + ((lng - point[1]) * 88.0) ** 2)


def feature_matrix(block):
    """한 기점의 동별 구조 변수. 결측은 같은 구의 중앙값으로 채운다."""
    frame = block.copy()
    frame["log_ppm2"] = np.log(frame["ppm2"])
    frame["log_stock"] = np.log1p(frame["stock_hh"])
    frame["new_share"] = frame["completed_hh_8q"] / frame["stock_hh"].replace(0, np.nan)
    frame["dist_cbd"] = km_distance(frame["lat"], frame["lng"], CBD)
    frame["dist_gangnam"] = km_distance(frame["lat"], frame["lng"], GANGNAM)

    for column in STRUCTURE_COLUMNS:
        by_gu = frame.groupby("sggCd")[column].transform("median")
        frame[column] = frame[column].fillna(by_gu).fillna(frame[column].median())
    return frame[["dong", *STRUCTURE_COLUMNS]].dropna().reset_index(drop=True)
