"""78번 algorithm 비교에서 쓰는 fit과 purged validation helper."""

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet, LinearRegression
from sklearn.svm import SVR

SEED = 42
ELASTIC_GRID = ((0.0001, 0.2), (0.0001, 0.8), (0.001, 0.2), (0.001, 0.8), (0.01, 0.5))
RF_LEAF_GRID = (5, 20, 50)
SVR_GRID = ((0.1, "scale"), (1.0, "scale"), (10.0, "scale"))


def rel_mae(pred, target, origin):
    """기점별 상대 MAE를 계산한 뒤 기점에 같은 weight를 준다."""
    pred = np.asarray(pred, dtype=float)
    target = np.asarray(target, dtype=float)
    origin = np.asarray(origin)
    losses = []
    for value in np.unique(origin):
        take = origin == value
        rp = pred[take] - pred[take].mean()
        rt = target[take] - target[take].mean()
        losses.append(np.abs(rp - rt).mean())
    return float(np.mean(losses))


def inner_masks(train):
    """64번과 같은 마지막 24개 기점 validation 및 s+3≤t purge를 적용한다."""
    origins = np.sort(train.mi.unique())
    val_origins = origins[-24:]
    val_start = val_origins[0]
    return (train.mi.add(3).le(val_start).to_numpy(), train.mi.isin(val_origins).to_numpy())


def _score(model, x_fit, y_fit, x_val, y_val, val_origin):
    model.fit(x_fit, y_fit)
    return rel_mae(model.predict(x_val), y_val, val_origin)


def fit_ols(x, y):
    return LinearRegression(fit_intercept=False).fit(x, y)


def fit_elastic(train, x):
    fit, val = inner_masks(train)
    y = train.r.to_numpy()
    scores = []
    for alpha, ratio in ELASTIC_GRID:
        model = ElasticNet(alpha=alpha, l1_ratio=ratio, fit_intercept=False,
                           max_iter=20000, selection="cyclic", random_state=SEED)
        scores.append(_score(model, x[fit], y[fit], x[val], y[val], train.origin.to_numpy()[val]))
    alpha, ratio = ELASTIC_GRID[int(np.argmin(scores))]
    return ElasticNet(alpha=alpha, l1_ratio=ratio, fit_intercept=False, max_iter=20000,
                      selection="cyclic", random_state=SEED).fit(x, y), (alpha, ratio)


def fit_rf(train, x):
    fit, val = inner_masks(train)
    y = train.r.to_numpy()
    scores = []
    for leaf in RF_LEAF_GRID:
        model = RandomForestRegressor(n_estimators=300, min_samples_leaf=leaf,
                                      random_state=SEED, n_jobs=4)
        scores.append(_score(model, x[fit], y[fit], x[val], y[val], train.origin.to_numpy()[val]))
    leaf = RF_LEAF_GRID[int(np.argmin(scores))]
    model = RandomForestRegressor(n_estimators=300, min_samples_leaf=leaf,
                                  random_state=SEED, n_jobs=4).fit(x, y)
    return model, leaf


def fit_svr(train, x, max_rows=5000):
    """고정 seed로 training row를 제한하고 같은 subset에서 tuning과 final fit을 한다."""
    fit, val = inner_masks(train)
    y = train.r.to_numpy()
    fit_idx = np.flatnonzero(fit)
    if len(fit_idx) > max_rows:
        fit_idx = np.sort(np.random.default_rng(SEED).choice(fit_idx, max_rows, replace=False))
    scores = []
    for c_value, gamma in SVR_GRID:
        model = SVR(C=c_value, gamma=gamma, epsilon=0.001, kernel="rbf")
        scores.append(_score(model, x[fit_idx], y[fit_idx], x[val], y[val],
                             train.origin.to_numpy()[val]))
    c_value, gamma = SVR_GRID[int(np.argmin(scores))]
    final_idx = np.arange(len(train))
    if len(final_idx) > max_rows:
        final_idx = np.sort(np.random.default_rng(SEED).choice(final_idx, max_rows, replace=False))
    model = SVR(C=c_value, gamma=gamma, epsilon=0.001, kernel="rbf")
    return model.fit(x[final_idx], y[final_idx]), (c_value, gamma, len(final_idx))
