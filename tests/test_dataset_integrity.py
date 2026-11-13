"""Dataset-as-code integrity audit for data/eval_dataset.csv.

Guards against silent regressions as the dataset scales toward
100 questions: IDs, enums, numeric specs, prompt units, and the
golden-reference invariant (every Model A answer scores >= 90
with error "none").
"""
import pandas as pd

from src.ruminant_eval.evaluator import evaluate_csv
from src.ruminant_eval.numeric_scorer import parse_numeric_specs
from src.ruminant_eval.rubric import CATEGORIES

SPECIES = {"cattle", "sheep", "goat", "dairy_cattle", "beef_cattle", "all"}
REQUIRED = [
    "question_id",
    "category",
    "species",
    "prompt",
    "reference_answer",
    "expected_keywords",
    "model_a_response",
    "model_b_response",
]


def _dataset():
    return pd.read_csv("data/eval_dataset.csv", dtype=str, keep_default_na=False)


def test_ids_unique_and_sequential():
    df = _dataset()
    assert list(df["question_id"]) == [f"Q{i:02d}" for i in range(1, len(df) + 1)]


def test_no_empty_cells_in_required_columns():
    df = _dataset()
    for col in REQUIRED:
        assert col in df.columns, col
        assert not df[col].str.strip().eq("").any(), col


def test_categories_and_species_are_canonical():
    df = _dataset()
    assert set(df["category"]) <= set(CATEGORIES)
    assert set(df["species"]) <= SPECIES


def test_numeric_specs_parse_and_prompts_name_their_units():
    df = _dataset()
    n_targets = 0
    for _, row in df.iterrows():
        for spec in parse_numeric_specs(row["expected_numeric"]):
            n_targets += 1
            prompt = row["prompt"]
            if spec.unit == "%":
                assert "%" in prompt or "percentage" in prompt, row["question_id"]
            elif spec.unit == "kg":
                assert "kg" in prompt, row["question_id"]
            elif spec.unit == "L":
                assert "L" in prompt, row["question_id"]
            elif spec.unit == "mL":
                assert "mL" in prompt, row["question_id"]
            elif spec.unit == "g/kg":
                assert "g/kg" in prompt or "g CH4/kg" in prompt, row["question_id"]
            elif spec.unit == "g":
                assert "g N/day" in prompt, row["question_id"]
            elif spec.unit == "":
                assert any(
                    t in prompt
                    for t in ("ratio", "pH", "conversion ratio", "degrees of freedom", "how many")
                ), row["question_id"]
    assert n_targets == 19  # 18 quantitative prompts, Q09 has two targets


def test_golden_reference_invariant():
    scores = evaluate_csv("data/eval_dataset.csv")
    a = scores[scores["model"] == "A"]
    assert len(a) == 54
    assert (a["error"] == "none").all()
    assert (a["score"] >= 90.0).all()
