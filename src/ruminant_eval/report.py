"""Report generator for RuminantEval.

Renders reports/sample_evaluation_report.md from the locked dataset,
detecting the trial schema automatically:
- Trial 1: one-way ANOVA (WAD goat phytogenic trial, N=24)
- Trial 2: two-way factorial ANOVA (dairy concentrate x buffer/yeast, N=32)

The report is auto-generated and never edited by hand. A test
(tests/test_report_sync.py) renders it in memory and asserts it
matches the committed file, so a forgotten regeneration fails pytest.
"""
from pathlib import Path

import pandas as pd

from .evaluator import evaluate_csv
from .factorial_anova import assumption_checks, run_balanced_two_way_anova
from .trial import residual_assumptions, trial_summary


def _anova_table_md(result):
    lines = ["| Source | SS | df | MS | F | p |", "|---|---|---|---|---|---|"]
    for row in result.table:
        f = f"{row.f_stat:.2f}" if row.f_stat is not None else "-"
        p = f"{row.p_value:.4f}" if row.p_value is not None else "-"
        lines.append(f"| {row.source} | {row.ss:.3f} | {row.df} | {row.ms:.3f} | {f} | {p} |")
    return "\n".join(lines)


def _cell_means_md(result):
    lines = ["| Concentrate | Additive | Mean | SD | SEM |", "|---|---|---|---|---|"]
    for _, r in result.cell_summary.iterrows():
        lines.append(
            f"| {r['concentrate_level']} | {r['additive']} | {r['mean']:.2f} | {r['sd']:.2f} | {r['sem']:.2f} |"
        )
    return "\n".join(lines)


def _assumptions_md(checks):
    return (
        f"Assumption checks on residuals: Shapiro-Wilk W = {checks['shapiro_w']:.3f}, "
        f"p = {checks['shapiro_p']:.4f}; Levene W = {checks['levene_w']:.3f}, "
        f"p = {checks['levene_p']:.4f}."
    )


def render_report(base_dir="."):
    """Render the full markdown report in memory from the current dataset."""
    base = Path(base_dir)
    scores = evaluate_csv(base / "data" / "eval_dataset.csv")
    goat_df = pd.read_csv(base / "data" / "trial_data.csv")
    goat = trial_summary(goat_df)
    goat_checks = residual_assumptions(goat_df)
    dairy = pd.read_csv(base / "data" / "trial_dairy_2x2.csv")

    lines = [
        "# RuminantEval — Sample Evaluation Report",
        "",
        "Phase 3 — numeric extraction & scoring, plus two-way factorial trial.",
        f"Questions evaluated: {scores['question_id'].nunique()}",
        f"Answers scored: {len(scores)}",
        f"Mean score: {scores['score'].mean():.1f} / 100",
        "",
        "## Mean score by model",
        "",
        scores.groupby("model")["score"].mean().to_string(),
        "",
        "## Error distribution",
        "",
        scores["error"].value_counts().to_string(),
        "",
        "## Safety-zero cases (dangerous advice, score 0)",
        "",
    ]
    for _, r in scores[(scores["error"] == "dangerous_advice")].iterrows():
        lines.append(f"- {r['question_id']} (Model {r['model']}): {r['dangerous_claims']}")
    lines += [
        "",
        "Q01 methane-as-nutrient is a standard factual error, not a safety zero.",
        "",
        "## Numeric-error cases (Phase 3)",
        "",
    ]
    for _, r in scores[(scores["error"] == "numeric_error")].iterrows():
        lines.append(f"- {r['question_id']} (Model {r['model']}, score {r['score']}): {r['numeric_details']}")
    lines += [
        "",
        "All Model A answers pass their numeric targets and classify as no error.",
        "",
        "## Trial 1: One-Way ANOVA — WAD Goat Phytogenic Trial (N=24)",
        "",
        f"ANOVA F = {goat['anova_f']}, p = {goat['anova_p']}, significant = {goat['significant']}",
        f"Best treatment by mean daily gain: {goat['best_treatment_by_mean_gain']}",
        _assumptions_md(goat_checks),
        "",
        "## Trial 2: Two-Way Factorial ANOVA — Dairy Concentrate × Buffer/Yeast (N=32)",
        "",
        "32 lactating Holsteins, 8 cows per cell. Factor A: concentrate level (Low_40 vs High_65 % DM). "
        "Factor B: rumen buffer / live yeast (Control vs Buffer_Yeast).",
        "",
    ]
    for response in ("rumen_ph", "milk_yield_kg", "milk_fat_pct"):
        result = run_balanced_two_way_anova(dairy, response=response)
        lines += [
            f"### {response}",
            "",
            _cell_means_md(result),
            "",
            _anova_table_md(result),
            "",
            _assumptions_md(assumption_checks(dairy, response=response)),
            "",
        ]
    return "\n".join(lines) + "\n"


def build_report(base_dir=".", output="reports/sample_evaluation_report.md"):
    """Regenerate reports/eval_scores.csv and the markdown report on disk."""
    base = Path(base_dir)
    scores = evaluate_csv(base / "data" / "eval_dataset.csv")
    scores.to_csv(base / "reports" / "eval_scores.csv", index=False)
    out = base / output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(base_dir), encoding="utf-8")
    return str(out)


if __name__ == "__main__":
    print(build_report())
