"""Feed-trial analysis for a synthetic West African Dwarf goat trial.

The trial design mirrors a real feeding trial: three treatments
(control, phytogenic additive at 0.5%, phytogenic additive at 1.0%),
with daily weight gain as the main outcome. All data is synthetic,
labelled as such, and is only used to demonstrate the analysis —
never publish real trial data without permission.

Analysis: group means, and a one-way ANOVA on daily gain.
A p-value below 0.05 means the treatments differ more than chance
alone would explain; it does not by itself say which treatment
is best — read the group means for that.
"""
import pandas as pd
from scipy import stats


def load_trial(path):
    return pd.read_csv(path)


def group_means(df, value="daily_gain_g"):
    """Mean, standard deviation and count per treatment."""
    return df.groupby("treatment")[value].agg(["mean", "std", "count"]).reset_index()


def anova_daily_gain(df, value="daily_gain_g"):
    """One-way ANOVA on daily gain across treatments."""
    groups = [g[value].values for _, g in df.groupby("treatment")]
    result = stats.f_oneway(*groups)
    return {"f_statistic": float(result.statistic), "p_value": float(result.pvalue)}


def residual_assumptions(df, value="daily_gain_g", group="treatment"):
    """Parametric assumption checks on ANOVA residuals.

    Shapiro-Wilk tests normality of the residuals (value minus its
    group mean); Levene tests homogeneity of variance across groups.
    A p-value above 0.05 means the assumption is not rejected.
    """
    groups = [g[value].values for _, g in df.groupby(group)]
    residuals = df[value] - df.groupby(group)[value].transform("mean")
    shapiro = stats.shapiro(residuals)
    levene = stats.levene(*groups)
    return {
        "shapiro_w": float(shapiro.statistic),
        "shapiro_p": float(shapiro.pvalue),
        "levene_w": float(levene.statistic),
        "levene_p": float(levene.pvalue),
    }


def trial_summary(df):
    """Plain summary a researcher can read without running code."""
    means = group_means(df)
    anova = anova_daily_gain(df)
    best = means.loc[means["mean"].idxmax(), "treatment"]
    return {
        "treatments": means.to_dict(orient="records"),
        "anova_f": round(anova["f_statistic"], 2),
        "anova_p": round(anova["p_value"], 4),
        "significant": anova["p_value"] < 0.05,
        "best_treatment_by_mean_gain": best,
    }
