"""Workstream 3 scale checks: 54 questions, 9 per category, calibrated error mix."""
import pandas as pd

from src.ruminant_eval.evaluator import evaluate_csv


def test_dataset_has_54_questions_9_per_category():
    df = pd.read_csv("data/eval_dataset.csv")
    assert len(df) == 54
    counts = df["category"].value_counts()
    assert set(counts.index) == {
        "production_systems",
        "nutrition_and_feeding",
        "methane_and_environment",
        "animal_health",
        "rumen_health",
        "experimental_methods",
    }
    assert all(counts == 9)


def test_error_calibration_across_54_questions():
    scores = evaluate_csv("data/eval_dataset.csv")
    assert len(scores) == 108
    b = scores[scores["model"] == "B"]
    errors = b["error"].value_counts()
    assert errors["dangerous_advice"] == 10
    assert errors["numeric_error"] == 18
    assert errors["omission"] + errors["hallucination"] == 26
    # Every Model A answer classifies as no error.
    a = scores[scores["model"] == "A"]
    assert (a["error"] == "none").all()


def test_new_numeric_items_trigger():
    scores = evaluate_csv("data/eval_dataset.csv")
    for qid in ("Q19", "Q20", "Q22", "Q23", "Q24", "Q26", "Q28", "Q29",
                "Q39", "Q40", "Q43", "Q48", "Q50", "Q53"):
        row = scores[(scores["question_id"] == qid) & (scores["model"] == "B")].iloc[0]
        assert row["error"] == "numeric_error", qid
        a_row = scores[(scores["question_id"] == qid) & (scores["model"] == "A")].iloc[0]
        assert a_row["error"] == "none", qid


def test_new_dangerous_items_score_zero():
    scores = evaluate_csv("data/eval_dataset.csv")
    for qid in ("Q34", "Q35", "Q36", "Q41", "Q42", "Q54"):
        row = scores[(scores["question_id"] == qid) & (scores["model"] == "B")].iloc[0]
        assert row["error"] == "dangerous_advice", qid
        assert row["score"] == 0.0, qid
