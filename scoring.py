"""
Scoring and grading calculation module for the Peer Evaluation System.

This module handles:
- Weighted percentage calculation for individual evaluations
- Aggregation of scores across multiple evaluators (mean, median, trimmed mean)
- Curved grading with protection thresholds
- Letter grade assignment
"""

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

    Takes multiple evaluations for each student and computes an aggregate score.
    
    Args:
        df_eval: DataFrame with columns ["Evaluatee", "Team", "Evaluator", "Score %"]
        method: Aggregation method - "mean", "median", or "trimmed_mean"
        trim_fraction: Fraction to trim from each tail when method == "trimmed_mean"
                      (e.g., 0.1 trims 10% from top and bottom)
    
    Returns:
        DataFrame with columns ["Evaluatee", "Team", "Avg_Score_Pct", "N_Evals"]
        where Avg_Score_Pct is the aggregated score and N_Evals is the count
    """
    method = (method or "mean").lower().strip()
    if df_eval.empty:
        # Return empty DataFrame with correct structure
        return pd.DataFrame(columns=["Evaluatee", "Team", "Avg_Score_Pct", "N_Evals"])\
                 .astype({"Avg_Score_Pct": "float64", "N_Evals": "int64"})

    if method == "median":
        # Use median to reduce impact of outliers
        grouped = df_eval.groupby(["Evaluatee", "Team"]).agg(
            Avg_Score_Pct=("Score %", "median"),
            N_Evals=("Score %", "count"),
        )
    elif method == "trimmed_mean":
        # Trim equally from both tails before averaging (removes outliers)
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
            # Return mean of trimmed series (excluding k lowest and k highest)
            return float(s_sorted.iloc[k:n - k].mean())

        grouped = df_eval.groupby(["Evaluatee", "Team"]).agg(
            Avg_Score_Pct=("Score %", trimmed_mean),
            N_Evals=("Score %", "count"),
        )
    else:  # default: simple arithmetic mean
        grouped = df_eval.groupby(["Evaluatee", "Team"]).agg(
            Avg_Score_Pct=("Score %", "mean"),
            N_Evals=("Score %", "count"),
        )

    result = grouped.reset_index().sort_values(["Team", "Evaluatee"]).copy()
    result["Avg_Score_Pct"] = result["Avg_Score_Pct"].round(2)
    return result


def compute_letter_grade(percent: float) -> str:
    """Map percentage score to letter grade using standard grading scale.
    
    Args:
        percent: Numeric percentage score (0-100)
    
    Returns:
        Letter grade: "A" (90+), "B" (80-89), "C" (70-79), "D" (60-69), "F" (<60)
    """
    p = float(percent)
    if p >= 90.0:
        return "A"
    if p >= 80.0:
        return "B"
    if p >= 70.0:
        return "C"
    if p >= 60.0:
        return "D"
    return "F"


def apply_curve_scores(
    df_scores: pd.DataFrame,
    protect_threshold: float = 80.0,
    k: float = 0.5,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """Apply curved grading to aggregated scores.

    Implements a protection-based curve: students scoring above the threshold
    are not adjusted, while lower scores are boosted toward the mean.
    
    Formula for scores below threshold: adjusted = raw + k * (mean - raw)
    This pulls lower scores up toward the class average.
    
    Args:
        df_scores: DataFrame with columns ["Evaluatee", "Team", "Avg_Score_Pct", "N_Evals"]
        protect_threshold: Percentages >= this value are not adjusted (default 80.0)
        k: Boosting factor in [0,1]. Higher k = more aggressive curve (default 0.5)

    Returns:
        Tuple of (df_with_curved_columns, stats)
        - df includes new columns: Curved_Score_Pct, Letter_Grade
        - stats dict includes: mean, std, k, protect_threshold
    """
    if df_scores.empty:
        # Return empty DataFrame with correct structure
        return df_scores.assign(Curved_Score_Pct=df_scores.get("Avg_Score_Pct", pd.Series(dtype="float64")),
                                Letter_Grade=""), {"mean": 0.0, "std": 0.0, "k": k, "protect_threshold": protect_threshold}

    # Calculate class statistics for curve calculation
    raw = df_scores["Avg_Score_Pct"].astype(float)
    mean_val = float(raw.mean()) if len(raw) else 0.0
    std_val = float(raw.std(ddof=0)) if len(raw) else 0.0

    def adjust(x: float) -> float:
        """Apply curve adjustment to a single score.
        
        Scores at or above threshold are unchanged.
        Scores below threshold are boosted toward the mean.
        """
        if x >= protect_threshold:
            return float(x)  # Protected scores remain unchanged
        # Boost lower scores: move toward mean by factor k
        return float(x + k * (mean_val - x))

    # Apply curve adjustment and compute letter grades
    curved = raw.apply(adjust).round(2)
    letters = curved.apply(compute_letter_grade)
    
    # Add new columns to output DataFrame
    out = df_scores.copy()
    out["Curved_Score_Pct"] = curved
    out["Letter_Grade"] = letters
    
    # Return statistics for reference
    stats = {"mean": mean_val, "std": std_val, "k": float(k), "protect_threshold": float(protect_threshold)}
    return out, stats


