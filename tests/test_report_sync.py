"""The committed report must match a fresh render, byte for byte.

reports/sample_evaluation_report.md is auto-generated and never
edited by hand. If a question, threshold or ANOVA result changes
and the report is not regenerated, this test fails immediately.
"""
from pathlib import Path

from src.ruminant_eval.report import render_report


def test_committed_report_matches_fresh_render():
    committed = Path("reports/sample_evaluation_report.md").read_text(encoding="utf-8")
    assert render_report() == committed
