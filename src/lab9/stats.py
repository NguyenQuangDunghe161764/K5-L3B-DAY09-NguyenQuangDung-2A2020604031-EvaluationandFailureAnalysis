"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge sequences must have the same length")
    h = [str(v).strip().upper() for v in human]
    j = [str(v).strip().upper() for v in judge]
    if not h:
        raise ValueError("sequences must not be empty")
    if any(v not in {"PASS", "FAIL"} for v in h + j):
        raise ValueError("labels must be PASS or FAIL")
    return {
        "tp": sum(hv == "FAIL" and jv == "FAIL" for hv, jv in zip(h, j)),
        "fp": sum(hv == "PASS" and jv == "FAIL" for hv, jv in zip(h, j)),
        "fn": sum(hv == "FAIL" and jv == "PASS" for hv, jv in zip(h, j)),
        "tn": sum(hv == "PASS" and jv == "PASS" for hv, jv in zip(h, j)),
    }


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    # TODO M2: precision = tp/(tp+fp), recall = tp/(tp+fn); return 0.0 when the denominator is 0
    cm = confusion(human, judge)
    precision = cm["tp"] / (cm["tp"] + cm["fp"]) if cm["tp"] + cm["fp"] else 0.0
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if cm["tp"] + cm["fn"] else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = sum(cm.values())
    p_obs = (cm["tp"] + cm["tn"]) / n
    human_fail = cm["tp"] + cm["fn"]
    judge_fail = cm["tp"] + cm["fp"]
    human_pass = cm["tn"] + cm["fp"]
    judge_pass = cm["tn"] + cm["fn"]
    p_e = (human_fail * judge_fail + human_pass * judge_pass) / (n * n)
    if p_e == 1.0:
        raise ValueError("kappa undefined: expected agreement is 1")
    return (p_obs - p_e) / (1.0 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    if not 0.0 <= observed_rate <= 1.0:
        raise ValueError("observed_rate must be in [0, 1]")
    if not 0.0 <= sensitivity <= 1.0 or not 0.0 <= specificity <= 1.0:
        raise ValueError("sensitivity and specificity must be in [0, 1]")
    denominator = sensitivity + specificity - 1.0
    if denominator == 0:
        raise ValueError("Rogan-Gladen correction undefined")
    corrected = (observed_rate + specificity - 1.0) / denominator
    return max(0.0, min(1.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    if len(a) != len(b):
        raise ValueError("paired samples must have the same length")
    if not a:
        raise ValueError("paired samples must not be empty")
    import numpy as np
    from scipy.stats import bootstrap
    mean_a = float(np.mean(a))
    mean_b = float(np.mean(b))
    d = mean_a - mean_b
    if all(float(x) == float(y) for x, y in zip(a, b)):
        return d, d, d
    def statistic(x: np.ndarray, y: np.ndarray) -> float:
        return float(np.mean(x) - np.mean(y))
    result = bootstrap((np.asarray(a, dtype=float), np.asarray(b, dtype=float)),
                       statistic, paired=True, method="percentile",
                       n_resamples=n_resamples, confidence_level=confidence,
                       rng=np.random.default_rng(rng))
    lo, hi = (float(result.confidence_interval.low), float(result.confidence_interval.high))
    return d, lo, hi


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    import math
    if k <= 0 or k > n or n < 0 or c < 0 or c > n:
        raise ValueError("invalid n, c, k")
    if k > n:
        raise ValueError("k > n")
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    import math
    if k <= 0 or k > n or n < 0 or c < 0 or c > n:
        raise ValueError("invalid n, c, k")
    denominator = math.comb(n, k)
    return math.comb(c, k) / denominator
