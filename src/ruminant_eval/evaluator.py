"""Rule-based demo scorer for ruminant nutrition answers.

This is a transparent, deterministic scorer for the demo dataset:
it checks whether the answer contains the expected keywords from
the golden reference, and whether it contains a dangerous claim.
It is not a replacement for human review — it is a reproducible
baseline you can compare models against, the same way a human
evaluator would use a rubric first and judgement second.

Synonyms are matched on whole tokens only, so "CP" matches crude
protein but not "accept" or "chapter", and "CH4" / "CH₄" match
methane. See SYNONYMS below.
"""
import argparse
import re

import pandas as pd

from .numeric_scorer import evaluate_numeric_response
from .safety import flag_dangerous_advice

# Removing the factual_accuracy component (30% weight) when a
# numeric target fails.
NUMERIC_PENALTY = 30.0

# Canonical keyword -> accepted forms. Keys are the forms used in
# expected_keywords in the dataset; values include abbreviations
# and chemical formulas a correct answer may use instead.
SYNONYMS = {
    "methane": ["methane", "ch4", "ch₄"],
    "ch4": ["ch4", "ch₄", "methane"],
    "crude protein": ["crude protein", "cp"],
    "volatile fatty acids": ["volatile fatty acids", "vfa"],
    "neutral detergent fibre": [
        "neutral detergent fibre",
        "neutral detergent fiber",
        "ndf",
    ],
    "feed conversion ratio": ["feed conversion ratio", "fcr"],
    "average daily gain": ["average daily gain", "adg"],
    "rumen fermentation": ["rumen fermentation"],
    "greenhouse gas": ["greenhouse gas"],
    "feed energy": ["feed energy"],
}


def _matches_token(text, phrase):
    """Whole-token match: (?<!\\w)phrase(?!\\w), so "cp" does not
    match inside "accept", and "ch4" does not match "chapter"."""
    pattern = r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)"
    return re.search(pattern, text.lower()) is not None


def keyword_score(response, expected_keywords):
    """Fraction of expected keywords present in the response,
    counting accepted synonyms as a match."""
    if not expected_keywords:
        return 0.0
    found = 0
    for kw in expected_keywords:
        kw = kw.strip().lower()
        forms = SYNONYMS.get(kw, [kw])
        if any(_matches_token(response, form) for form in forms):
            found += 1
    return found / len(expected_keywords)


def classify_error(response, expected_keywords, expected_numeric=None, prompt=None):
    """Classify the main error in a response, or 'none'."""
    if flag_dangerous_advice(response):
        return "dangerous_advice"
    if expected_numeric and not evaluate_numeric_response(response, expected_numeric, prompt).passed:
        return "numeric_error"
    if keyword_score(response, expected_keywords) == 0:
        return "hallucination"
    if keyword_score(response, expected_keywords) < 0.5:
        return "omission"
    return "none"


def score_response(response, expected_keywords, expected_numeric=None, prompt=None):
    """Score one response 0-100, using keyword coverage as a proxy
    for factual accuracy, 0 if it contains dangerous advice, and
    minus 30 (the factual_accuracy weight) if a numeric target fails."""
    if flag_dangerous_advice(response):
        return 0.0
    base = keyword_score(response, expected_keywords) * 100
    if expected_numeric and not evaluate_numeric_response(response, expected_numeric, prompt).passed:
        base -= NUMERIC_PENALTY
    return round(max(0.0, base), 1)


def evaluate_csv(input_path, output_path=None):
    """Score every row in an evaluation CSV and return the results."""
    df = pd.read_csv(input_path)
    rows = []
    for _, row in df.iterrows():
        keywords = [k.strip() for k in str(row["expected_keywords"]).split(";")]
        numeric_spec = ""
        if "expected_numeric" in df.columns and pd.notna(row.get("expected_numeric")):
            numeric_spec = str(row["expected_numeric"])
        prompt = str(row["prompt"]) if "prompt" in df.columns and pd.notna(row.get("prompt")) else None
        for model in ("model_a_response", "model_b_response"):
            response = str(row[model])
            numeric = evaluate_numeric_response(response, numeric_spec, prompt) if numeric_spec else None
            rows.append(
                {
                    "question_id": row["question_id"],
                    "category": row["category"],
                    "model": "A" if model == "model_a_response" else "B",
                    "score": score_response(response, keywords, numeric_spec, prompt),
                    "error": classify_error(response, keywords, numeric_spec, prompt),
                    "dangerous_claims": "; ".join(flag_dangerous_advice(response)),
                    "numeric_details": "; ".join(numeric.details) if numeric else "",
                }
            )
    result = pd.DataFrame(rows)
    if output_path:
        result.to_csv(output_path, index=False)
    return result


def main():
    parser = argparse.ArgumentParser(description="Evaluate ruminant nutrition answers.")
    parser.add_argument("--input", required=True, help="Evaluation CSV file.")
    parser.add_argument("--output", default=None, help="Output CSV for scores.")
    args = parser.parse_args()
    result = evaluate_csv(args.input, args.output)
    print(result.to_string(index=False))
    print(f"\nMean score: {result['score'].mean():.1f} / 100")
    print(result["error"].value_counts().to_string())


if __name__ == "__main__":
    main()
