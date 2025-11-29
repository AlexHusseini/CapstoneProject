"""Tests for scoring functions."""
import pytest
import pandas as pd
from scoring import (
    compute_weighted_percentage,
    aggregate_scores_df,
    compute_letter_grade,
    apply_curve_scores
)


def test_compute_weighted_percentage():
    """Test weighted percentage calculation."""
    scores = {"1": 4, "2": 5}
    rubric_items = {
        "1": ("Quality", 2.0, 5),
        "2": ("Communication", 1.0, 5)
    }
    result = compute_weighted_percentage(scores, rubric_items)
    # (4/5 * 2.0 + 5/5 * 1.0) / 3.0 * 100 = (0.8 * 2 + 1.0 * 1) / 3 * 100 = 2.6/3 * 100 = 86.67
    assert result > 86.0
    assert result < 87.0


def test_compute_weighted_percentage_zero_scores():
    """Test weighted percentage with zero scores."""
    scores = {"1": 0, "2": 0}
    rubric_items = {
        "1": ("Quality", 1.0, 5),
        "2": ("Communication", 1.0, 5)
    }
    result = compute_weighted_percentage(scores, rubric_items)
    assert result == 0.0


def test_compute_weighted_percentage_missing_scores():
    """Test weighted percentage with missing scores."""
    scores = {"1": 3}
    rubric_items = {
        "1": ("Quality", 1.0, 5),
        "2": ("Communication", 1.0, 5)
    }
    result = compute_weighted_percentage(scores, rubric_items)
    # (3/5 * 1.0 + 0/5 * 1.0) / 2.0 * 100 = 0.6/2 * 100 = 30.0
    assert result == 30.0


def test_compute_letter_grade():
    """Test letter grade computation."""
    assert compute_letter_grade(95.0) == "A"
    assert compute_letter_grade(90.0) == "A"
    assert compute_letter_grade(85.0) == "B"
    assert compute_letter_grade(80.0) == "B"
    assert compute_letter_grade(75.0) == "C"
    assert compute_letter_grade(70.0) == "C"
    assert compute_letter_grade(65.0) == "D"
    assert compute_letter_grade(60.0) == "D"
    assert compute_letter_grade(55.0) == "F"
    assert compute_letter_grade(0.0) == "F"


def test_aggregate_scores_df_mean():
    """Test score aggregation using mean."""
    df = pd.DataFrame({
        "Evaluatee": ["Alice", "Alice", "Bob"],
        "Team": ["Team A", "Team A", "Team B"],
        "Evaluator": ["Bob", "Charlie", "Alice"],
        "Score %": [80.0, 90.0, 85.0]
    })
    result = aggregate_scores_df(df, method="mean")
    assert len(result) == 2
    assert result[result["Evaluatee"] == "Alice"]["Avg_Score_Pct"].values[0] == 85.0
    assert result[result["Evaluatee"] == "Bob"]["Avg_Score_Pct"].values[0] == 85.0


def test_aggregate_scores_df_median():
    """Test score aggregation using median."""
    df = pd.DataFrame({
        "Evaluatee": ["Alice", "Alice", "Alice"],
        "Team": ["Team A", "Team A", "Team A"],
        "Evaluator": ["Bob", "Charlie", "David"],
        "Score %": [70.0, 80.0, 90.0]
    })
    result = aggregate_scores_df(df, method="median")
    assert len(result) == 1
    assert result["Avg_Score_Pct"].values[0] == 80.0


def test_aggregate_scores_df_empty():
    """Test score aggregation with empty dataframe."""
    df = pd.DataFrame(columns=["Evaluatee", "Team", "Evaluator", "Score %"])
    result = aggregate_scores_df(df)
    assert len(result) == 0
    assert list(result.columns) == ["Evaluatee", "Team", "Avg_Score_Pct", "N_Evals"]


def test_apply_curve_scores():
    """Test curve application to scores."""
    df = pd.DataFrame({
        "Evaluatee": ["Alice", "Bob", "Charlie"],
        "Team": ["Team A", "Team A", "Team B"],
        "Avg_Score_Pct": [70.0, 80.0, 90.0],
        "N_Evals": [3, 3, 3]
    })
    result, stats = apply_curve_scores(df, protect_threshold=80.0, k=0.5)
    assert "Curved_Score_Pct" in result.columns
    assert "Letter_Grade" in result.columns
    # Score >= 80 should not be adjusted
    assert result[result["Evaluatee"] == "Charlie"]["Curved_Score_Pct"].values[0] == 90.0
    # Score < 80 should be adjusted
    assert result[result["Evaluatee"] == "Alice"]["Curved_Score_Pct"].values[0] > 70.0


def test_apply_curve_scores_empty():
    """Test curve application with empty dataframe."""
    df = pd.DataFrame(columns=["Evaluatee", "Team", "Avg_Score_Pct", "N_Evals"])
    result, stats = apply_curve_scores(df, protect_threshold=80.0, k=0.5)
    assert len(result) == 0
    assert "Curved_Score_Pct" in result.columns
    assert "Letter_Grade" in result.columns


