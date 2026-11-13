"""Balanced two-way factorial ANOVA — Phase 3, Workstream 2.

Built strictly on numpy, pandas and scipy.stats (no statsmodels).
For a balanced, completely crossed design the Type I and Type III
sums of squares are the same, so the partition below is exact:
SS_total = SS_A + SS_B + SS_AxB + SS_error.

Trial 2: 2x2 factorial lactating Holstein trial, N=32, n=8/cell.
Factor A: concentrate level (Low_40 vs High_65 % DM).
Factor B: rumen buffer / live yeast (Control vs Buffer_Yeast).
Responses: rumen_ph, milk_yield_kg, milk_fat_pct.
"""
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class AnovaRow:
    source: str
    ss: float
    df: int
    ms: float
    f_stat: float | None
    p_value: float | None


@dataclass(frozen=True)
class TwoWayAnovaResult:
    response: str
    factor_a: str
    factor_b: str
    n_per_cell: int
    table: list[AnovaRow]
    cell_summary: pd.DataFrame


def generate_dairy_2x2_trial(output_path: str | Path | None = None, seed: int = 2026) -> pd.DataFrame:
    """Generate a reproducible 2x2 factorial lactating Holstein dataset (N=32, n=8/cell)."""
    rng = np.random.default_rng(seed)

    # Cell parameters: (concentrate_level, additive): (ph_mean, ph_sd, yield_mean, yield_sd, fat_mean, fat_sd)
    cell_specs = {
        ("Low_40", "Control"): (6.32, 0.10, 31.5, 1.7, 3.85, 0.16),
        ("Low_40", "Buffer_Yeast"): (6.36, 0.10, 32.0, 1.7, 3.88, 0.16),
        ("High_65", "Control"): (5.64, 0.11, 35.8, 1.9, 3.15, 0.20),
        ("High_65", "Buffer_Yeast"): (6.08, 0.10, 37.4, 1.9, 3.62, 0.18),
    }

    rows: list[dict] = []
    cow_num = 1
    for (conc, add), (ph_m, ph_sd, y_m, y_sd, f_m, f_sd) in cell_specs.items():
        ph_vals = np.round(rng.normal(ph_m, ph_sd, size=8), 2)
        yield_vals = np.round(rng.normal(y_m, y_sd, size=8), 2)
        fat_vals = np.round(rng.normal(f_m, f_sd, size=8), 2)

        for ph, my, fat in zip(ph_vals, yield_vals, fat_vals):
            rows.append(
                {
                    "cow_id": f"HOL-{cow_num:02d}",
                    "concentrate_level": conc,
                    "additive": add,
                    "rumen_ph": float(ph),
                    "milk_yield_kg": float(my),
                    "milk_fat_pct": float(fat),
                }
            )
            cow_num += 1

    df = pd.DataFrame(rows)
    if output_path is not None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
    return df


def assumption_checks(
    df: pd.DataFrame,
    response: str,
    factor_a: str = "concentrate_level",
    factor_b: str = "additive",
) -> dict:
    """Parametric assumption checks on two-way ANOVA residuals.

    Shapiro-Wilk tests normality of the residuals (response minus its
    cell mean); Levene tests homogeneity of variance across cells.
    A p-value above 0.05 means the assumption is not rejected.
    """
    cell_means = df.groupby([factor_a, factor_b])[response].transform("mean")
    residuals = df[response] - cell_means
    groups = [g[response].values for _, g in df.groupby([factor_a, factor_b])]
    shapiro = stats.shapiro(residuals)
    levene = stats.levene(*groups)
    return {
        "shapiro_w": float(shapiro.statistic),
        "shapiro_p": float(shapiro.pvalue),
        "levene_w": float(levene.statistic),
        "levene_p": float(levene.pvalue),
    }


def run_balanced_two_way_anova(
    df: pd.DataFrame,
    response: str,
    factor_a: str = "concentrate_level",
    factor_b: str = "additive",
) -> TwoWayAnovaResult:
    """Compute exact Type I/III orthogonal Two-Way ANOVA for a balanced factorial design."""
    required = {factor_a, factor_b, response}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    counts = df.groupby([factor_a, factor_b])[response].count()
    levels_a = df[factor_a].nunique()
    levels_b = df[factor_b].nunique()

    if len(counts) != levels_a * levels_b or counts.nunique() != 1:
        raise ValueError("Design must be completely crossed and balanced (equal n per cell).")

    n = int(counts.iloc[0])
    if n < 2:
        raise ValueError("At least 2 replicates per cell are required to estimate error variance.")

    total_n = len(df)
    grand_mean = float(df[response].mean())

    a_means = df.groupby(factor_a)[response].mean()
    b_means = df.groupby(factor_b)[response].mean()
    cell_stats = (
        df.groupby([factor_a, factor_b])[response]
        .agg(n="count", mean="mean", sd="std")
        .reset_index()
    )
    cell_stats["sem"] = cell_stats["sd"] / np.sqrt(cell_stats["n"])

    ss_total = float(((df[response] - grand_mean) ** 2).sum())
    ss_a = float(levels_b * n * ((a_means - grand_mean) ** 2).sum())
    ss_b = float(levels_a * n * ((b_means - grand_mean) ** 2).sum())
    ss_cells = float(n * ((cell_stats["mean"] - grand_mean) ** 2).sum())
    ss_ab = ss_cells - ss_a - ss_b

    merged = df.merge(cell_stats[[factor_a, factor_b, "mean"]], on=[factor_a, factor_b])
    ss_error = float(((merged[response] - merged["mean"]) ** 2).sum())

    df_a = levels_a - 1
    df_b = levels_b - 1
    df_ab = df_a * df_b
    df_error = levels_a * levels_b * (n - 1)
    df_total = total_n - 1

    ms_a = ss_a / df_a
    ms_b = ss_b / df_b
    ms_ab = ss_ab / df_ab
    ms_error = ss_error / df_error

    f_a = ms_a / ms_error
    f_b = ms_b / ms_error
    f_ab = ms_ab / ms_error

    p_a = float(stats.f.sf(f_a, df_a, df_error))
    p_b = float(stats.f.sf(f_b, df_b, df_error))
    p_ab = float(stats.f.sf(f_ab, df_ab, df_error))

    table = [
        AnovaRow(factor_a, ss_a, df_a, ms_a, f_a, p_a),
        AnovaRow(factor_b, ss_b, df_b, ms_b, f_b, p_b),
        AnovaRow(f"{factor_a} × {factor_b}", ss_ab, df_ab, ms_ab, f_ab, p_ab),
        AnovaRow("Error (Within)", ss_error, df_error, ms_error, None, None),
        AnovaRow("Total", ss_total, df_total, ss_total / df_total, None, None),
    ]

    return TwoWayAnovaResult(
        response=response,
        factor_a=factor_a,
        factor_b=factor_b,
        n_per_cell=n,
        table=table,
        cell_summary=cell_stats,
    )
