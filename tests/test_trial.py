import pandas as pd

from src.ruminant_eval.trial import (
    group_means,
    anova_daily_gain,
    residual_assumptions,
    trial_summary,
)


def _sample_trial():
    return pd.DataFrame(
        {
            "treatment": ["Control"] * 4 + ["Phytogenic 0.5%"] * 4 + ["Phytogenic 1.0%"] * 4,
            "daily_gain_g": [45, 48, 44, 47, 58, 61, 59, 62, 66, 68, 65, 69],
        }
    )


def test_group_means():
    means = group_means(_sample_trial())
    assert list(means["treatment"]) == ["Control", "Phytogenic 0.5%", "Phytogenic 1.0%"]
    assert means.iloc[0]["mean"] == 46.0


def test_anova_significant():
    result = anova_daily_gain(_sample_trial())
    assert result["p_value"] < 0.05


def test_trial_summary_best_treatment():
    summary = trial_summary(_sample_trial())
    assert summary["significant"] is True
    assert summary["best_treatment_by_mean_gain"] == "Phytogenic 1.0%"


def test_goat_trial_analysis_is_reproducible():
    # The goat CSV predates a generator (Phase 1, seed 42), so there
    # is no generator to match float-for-float. Instead, the analysis
    # itself must reproduce the locked report values on every run.
    df = pd.read_csv("data/trial_data.csv")
    assert len(df) == 24
    first = trial_summary(df)
    second = trial_summary(df)
    assert first == second
    assert first["anova_f"] == 155.77
    assert first["anova_p"] < 0.001
    assert first["best_treatment_by_mean_gain"] == "Phytogenic 1.0%"


def test_residual_assumptions_return_p_values():
    checks = residual_assumptions(_sample_trial())
    assert 0.0 <= checks["shapiro_p"] <= 1.0
    assert 0.0 <= checks["levene_p"] <= 1.0
    assert checks["shapiro_w"] > 0
    assert checks["levene_w"] >= 0
