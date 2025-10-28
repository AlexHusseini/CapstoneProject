from typing import Dict, Tuple

import pandas as pd


def compute_weighted_percentage(
    scores_by_criterion_id: Dict[str, int],
    rubric_items_by_id: Dict[str, Tuple[str, float, int]],
) -> float:
    """Compute a weighted percentage for a single evaluation submission.

    scores_by_criterion_id: mapping of rubric item id (as string) to the numeric score provided
    rubric_items_by_id: mapping of rubric item id (as string) to a tuple of
        (criterion_name, weight, max_score)

    Returns a percentage in [0, 100].
    """
    total_weight = 0.0
    weighted_sum = 0.0
    for cid, (_crit, weight, max_score) in rubric_items_by_id.items():
        total_weight += float(weight)
        val = int(scores_by_criterion_id.get(cid, 0))
        if max_score and max_score > 0:
            weighted_sum += (val / max_score) * float(weight)
    if total_weight <= 0:
        return 0.0
    return (weighted_sum / total_weight) * 100.0


def aggregate_scores_df(
    df_eval: pd.DataFrame,
    method: str = "mean",
    trim_fraction: float = 0.0,
) -> pd.DataFrame:
    """Aggregate per-evaluation percentages to per-student scores.

    df_eval columns: ["Evaluatee", "Team", "Evaluator", "Score %"]
    method: one of {"mean", "median", "trimmed_mean"}
    trim_fraction: fraction to trim from each tail when method == trimmed_mean
    """
    method = (method or "mean").lower().strip()
    if df_eval.empty:
        return pd.DataFrame(columns=["Evaluatee", "Team", "Avg_Score_Pct", "N_Evals"])\
                 .astype({"Avg_Score_Pct": "float64", "N_Evals": "int64"})

    if method == "median":
        grouped = df_eval.groupby(["Evaluatee", "Team"]).agg(
            Avg_Score_Pct=("Score %", "median"),
            N_Evals=("Score %", "count"),
        )
    elif method == "trimmed_mean":
        # Trim equally from both tails before averaging
        def trimmed_mean(s: pd.Series) -> float:
            n = len(s)
            if n == 0:
                return 0.0
            f = float(trim_fraction or 0.0)
            if f <= 0:
                return float(s.mean())
            k = int(n * f)
            if k <= 0:
                return float(s.mean())
            s_sorted = s.sort_values().reset_index(drop=True)
            if 2 * k >= n:
                return float(s.mean())
            return float(s_sorted.iloc[k:n - k].mean())

        grouped = df_eval.groupby(["Evaluatee", "Team"]).agg(
            Avg_Score_Pct=("Score %", trimmed_mean),
            N_Evals=("Score %", "count"),
        )
    else:  # default mean
        grouped = df_eval.groupby(["Evaluatee", "Team"]).agg(
            Avg_Score_Pct=("Score %", "mean"),
            N_Evals=("Score %", "count"),
        )

    result = grouped.reset_index().sort_values(["Team", "Evaluatee"]).copy()
    result["Avg_Score_Pct"] = result["Avg_Score_Pct"].round(2)
    return result


def compute_letter_grade(percent: float) -> str:
    """Map percentage to letter grade using fixed bounds."""
    p = float(percent)
    if p >= 90.0:
        return "A"
    if p >= 80.0:
        return "B"
    if p >= 70.0:
        return "C"
    if p >= 60.0:
        return "D"
    return "E"


def apply_curve_scores(
    df_scores: pd.DataFrame,
    protect_threshold: float = 80.0,
    k: float = 0.5,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Apply curved grading to aggregated scores.

    Parameters
    - df_scores: DataFrame with columns ["Evaluatee", "Team", "Avg_Score_Pct", "N_Evals"]
    - protect_threshold: percentages >= this value are not adjusted
    - k: boosting factor in [0,1]; adjusted = raw + k * (M - raw) for raw < threshold

    Returns (df_with_curved_columns, stats)
    - df includes columns: Curved_Score_Pct, Letter_Grade
    - stats includes: mean, std, k, protect_threshold
    """
    if df_scores.empty:
        return df_scores.assign(Curved_Score_Pct=df_scores.get("Avg_Score_Pct", pd.Series(dtype="float64")),
                                Letter_Grade=""), {"mean": 0.0, "std": 0.0, "k": k, "protect_threshold": protect_threshold}

    raw = df_scores["Avg_Score_Pct"].astype(float)
    mean_val = float(raw.mean()) if len(raw) else 0.0
    std_val = float(raw.std(ddof=0)) if len(raw) else 0.0

    def adjust(x: float) -> float:
        if x >= protect_threshold:
            return float(x)
        return float(x + k * (mean_val - x))

    curved = raw.apply(adjust).round(2)
    letters = curved.apply(compute_letter_grade)
    out = df_scores.copy()
    out["Curved_Score_Pct"] = curved
    out["Letter_Grade"] = letters
    stats = {"mean": mean_val, "std": std_val, "k": float(k), "protect_threshold": float(protect_threshold)}
    return out, stats


