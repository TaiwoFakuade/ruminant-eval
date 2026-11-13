import numpy as np
import pandas as pd
import pytest

from src.ruminant_eval.factorial_anova import (
    generate_dairy_2x2_trial,
    run_balanced_two_way_anova,
)


def test_dairy_trial_csv_matches_seed_2026_generator():
    # Seed-to-CSV determinism: the committed file must match the
    # fixed-seed generator float-for-float.
    pd.testing.assert_frame_equal(
        generate_dairy_2x2_trial(seed=2026),
        pd.read_csv("data/trial_dairy_2x2.csv"),
    )


def test_dairy_2x2_anova_partition_and_interaction():
    df = generate_dairy_2x2_trial(seed=2026)
    assert len(df) == 32

    res = run_balanced_two_way_anova(df, response="rumen_ph")
    rows = {r.source: r for r in res.table}

    # Exact orthogonal SS & df partition
    ss_sum = (
        rows["concentrate_level"].ss
        + rows["additive"].ss
        + rows["concentrate_level × additive"].ss
        + rows["Error (Within)"].ss
    )
    assert np.isclose(ss_sum, rows["Total"].ss, atol=1e-9)
    assert rows["Error (Within)"].df == 28
    assert rows["Total"].df == 31

    # Engineered Concentrate x Additive interaction on rumen pH must be significant.
    # With seed 2026 the observed values are F=11.92, p=0.0018 — significant
    # at p<0.01, not p<0.001, so the threshold here is the honest one.
    inter = rows["concentrate_level × additive"]
    assert inter.f_stat is not None and inter.f_stat > 10.0
    assert inter.p_value is not None and inter.p_value < 0.01

    # Physiological sanity: High_65 + Control enters SARA (<5.80), Buffer_Yeast rescues (>6.00)
    means = res.cell_summary.set_index(["concentrate_level", "additive"])["mean"]
    assert means[("High_65", "Control")] < 5.80
    assert means[("High_65", "Buffer_Yeast")] > 6.00


def test_milk_fat_interaction_and_means():
    df = generate_dairy_2x2_trial(seed=2026)
    res = run_balanced_two_way_anova(df, response="milk_fat_pct")
    rows = {r.source: r for r in res.table}
    inter = rows["concentrate_level × additive"]
    assert inter.p_value is not None and inter.p_value < 0.05
    means = res.cell_summary.set_index(["concentrate_level", "additive"])["mean"]
    # Milk fat depression on High_65 + Control, rescued by Buffer_Yeast
    assert means[("High_65", "Control")] < means[("High_65", "Buffer_Yeast")]
    assert means[("High_65", "Control")] < 3.4


def test_unbalanced_factorial_raises_value_error():
    df = generate_dairy_2x2_trial(seed=2026).iloc[:-1]  # Drop 1 cow -> unbalanced
    with pytest.raises(ValueError, match="balanced"):
        run_balanced_two_way_anova(df, response="rumen_ph")
