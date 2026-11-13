"""RuminantEval: AI evaluation for ruminant nutrition science."""
from .evaluator import evaluate_csv, score_response, classify_error
from .factorial_anova import (
    assumption_checks,
    generate_dairy_2x2_trial,
    run_balanced_two_way_anova,
)
from .numeric_scorer import evaluate_numeric_response, parse_numeric_specs
from .report import build_report, render_report
from .safety import flag_dangerous_advice, is_safe
from .trial import residual_assumptions, trial_summary, group_means, anova_daily_gain

__all__ = [
    "evaluate_csv",
    "score_response",
    "classify_error",
    "assumption_checks",
    "evaluate_numeric_response",
    "parse_numeric_specs",
    "build_report",
    "render_report",
    "flag_dangerous_advice",
    "is_safe",
    "residual_assumptions",
    "trial_summary",
    "group_means",
    "anova_daily_gain",
]
