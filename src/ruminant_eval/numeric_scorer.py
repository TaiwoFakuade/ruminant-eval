"""Numeric extraction and scoring for RuminantEval — Phase 3, Workstream 1.

Uses only the Python standard library (re, dataclasses). Numbers are
anchored to metric aliases and units, and arithmetic inputs on the
left side of "=" are deprioritised, so "9 ÷ 1.5 = 6.0" selects 6.0,
not 9. When a numeric target fails, the factual_accuracy component
(30% weight) is removed and the error is "numeric_error".
"""
from dataclasses import dataclass
import re

METRIC_ALIASES: dict[str, str] = {
    "cp": r"\b(?:cp|crude protein)\b",
    "fcr": r"\b(?:fcr|feed conversion ratio)\b",
    "water": r"\b(?:water|drinking water)\b",
    "ph": r"\b(?:ph|rumen ph)\b",
    "adg": r"\b(?:adg|average daily gain)\b",
    "nel": r"\b(?:nel|ne_l|net energy)\b",
    "ch4": r"\b(?:ch4|ch₄|methane)\b",
    # Phase 3, Workstream 3 — metrics for Q19-Q54.
    "ewes": r"\b(?:ewes|head|sheep|stocking)\b",
    "dmi": r"\b(?:dmi|dry matter intake)\b",
    "weaning_weight": r"\b(?:weaning weight|adjusted weight|205-day)\b",
    "sbm": r"\b(?:sbm|soybean meal)\b",
    "ca_p": r"\b(?:ca:p|calcium-to-phosphorus|ratio)\b",
    "dmd": r"\b(?:dmd|digestibility|apparent dm)\b",
    "ch4_yield": r"\b(?:ch4 yield|methane yield|g/kg)\b",
    "ym": r"\b(?:ym|conversion factor|gross energy)\b",
    "dose_ml": r"\b(?:dose|volume|fenbendazole|suspension)\b",
    "pendf": r"\b(?:pendf|physically effective ndf)\b",
    "net_gas": r"\b(?:net gas|corrected gas|gas volume)\b",
    "n_retained": r"\b(?:retained|retention|nitrogen balance)\b",
    "df_error": r"\b(?:df|degrees of freedom|error df)\b",
}

UNIT_NORMALIZATION: dict[str, str] = {
    "%": "%",
    "l": "L",
    "liter": "L",
    "liters": "L",
    "litre": "L",
    "litres": "L",
    "kg": "kg",
    "g": "g",
    "ml": "mL",
    "g/kg": "g/kg",
    "mcal": "Mcal",
    "mcal/kg": "Mcal/kg",
}

# Numbers may use thousands separators ("32,000 ewes"), which are
# stripped before conversion so the value is 32000, not 32 or 0.
NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*"
    r"(%|mL\b|g/kg\b|L\b|litres?\b|liters?\b|kg\b|g\b|Mcal(?:/kg)?\b)?",
    re.IGNORECASE,
)

SPEC_PATTERN = re.compile(
    r"^(?P<metric>[a-z0-9_]+)=(?P<target>[^\[\]]+)\[(?P<unit>[^\]]*)\]$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NumericSpec:
    metric: str
    mode: str  # "point" or "range"
    low: float
    high: float
    unit: str


@dataclass(frozen=True)
class NumericAuditResult:
    passed: bool
    error_type: str | None  # None or "numeric_error"
    details: list[str]


def parse_numeric_specs(raw_spec: str | None) -> list[NumericSpec]:
    """Parse 'cp=16-18[%]; water=100-130[L]' into NumericSpec objects."""
    if not raw_spec or not str(raw_spec).strip():
        return []

    specs: list[NumericSpec] = []
    for chunk in str(raw_spec).split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        match = SPEC_PATTERN.match(chunk)
        if not match:
            raise ValueError(f"Invalid expected_numeric spec: '{chunk}'")

        metric = match.group("metric").lower()
        target = match.group("target").strip()
        raw_unit = match.group("unit").strip().lower()
        unit = UNIT_NORMALIZATION.get(raw_unit, match.group("unit").strip())

        if "±" in target:
            val_str, tol_str = target.split("±", 1)
            val, tol = float(val_str), float(tol_str)
            specs.append(NumericSpec(metric, "point", val - tol, val + tol, unit))
        elif "-" in target:
            low_str, high_str = target.split("-", 1)
            specs.append(NumericSpec(metric, "range", float(low_str), float(high_str), unit))
        else:
            val = float(target)
            specs.append(NumericSpec(metric, "point", val, val, unit))

    return specs


def _is_equation_operand(text: str, end_pos: int) -> bool:
    """True if the number sits immediately before an operator leading to '=' (e.g., '9 ÷ 1.5 =')."""
    trailing = text[end_pos : end_pos + 18]
    return bool(re.match(r"^(?:\s*[a-zA-Z/%]+)?\s*[÷/×*+-]\s*\d+(?:\.\d+)?(?:\s*[a-zA-Z/%]+)?\s*=", trailing))


# Contrastive negations that mark a number as refuted, not asserted:
# "Rather than 12.0%, the true crude protein is 15.0%" or
# "Not 4.5 — FCR is 6.0". A refuted distractor is penalised +3 so
# proximity alone cannot grab it when it sits closer to the alias.
CONTRASTIVE_CUES = ("not", "unlike", "instead of", "rather than", "versus", "vs")


def _is_refuted(text: str, n_start: int) -> bool:
    """True if a contrastive negation appears in the 25 characters before a number."""
    preceding = text[max(0, n_start - 25) : n_start].lower()
    return any(re.search(rf"(?<!\w){re.escape(cue)}(?!\w)", preceding) for cue in CONTRASTIVE_CUES)


def _prompt_numbers(prompt: str | None) -> set[float]:
    """All numeric literals appearing in the question prompt."""
    if not prompt:
        return set()
    return {
        float(m.group(1).replace(",", ""))
        for m in NUMBER_PATTERN.finditer(prompt)
    }


def extract_metric_value(
    text: str,
    metric: str,
    expected_unit: str,
    prompt: str | None = None,
) -> float | None:
    """Find the most contextually relevant number for a metric based on alias & unit proximity."""
    alias_regex = METRIC_ALIASES.get(metric, rf"\b{re.escape(metric)}\b")
    alias_spans = [m.span() for m in re.finditer(alias_regex, text, re.IGNORECASE)]
    if not alias_spans:
        return None

    prompt_nums = _prompt_numbers(prompt)
    raw_candidates: list[tuple[int, int, float]] = []  # (priority_penalty, char_distance, value)

    for num_match in NUMBER_PATTERN.finditer(text):
        value = float(num_match.group(1).replace(",", ""))
        raw_unit = (num_match.group(2) or "").lower()
        norm_unit = UNIT_NORMALIZATION.get(raw_unit, num_match.group(2) or "")
        n_start, n_end = num_match.span()

        # Unit filtering / scoring
        if expected_unit:
            if norm_unit != expected_unit:
                continue
            unit_penalty = 0
        else:
            # Prefer dimensionless numbers when no unit is expected (e.g., FCR)
            unit_penalty = 0 if norm_unit == "" else 1

        operand_penalty = 2 if _is_equation_operand(text, n_end) else 0
        refuted_penalty = 3 if _is_refuted(text, n_start) else 0

        min_dist = min(
            0 if (n_start <= a_end and n_end >= a_start) else min(abs(n_start - a_end), abs(a_start - n_end))
            for a_start, a_end in alias_spans
        )
        raw_candidates.append((unit_penalty + operand_penalty + refuted_penalty, min_dist, value))

    if not raw_candidates:
        return None

    # Prompt-echo tie-breaker: a number that verbatim-matches a prompt
    # input is deprioritised (+1) — models echo the prompt before
    # answering — unless it is the only number in the response.
    candidates = [
        (penalty + (1 if len(raw_candidates) > 1 and value in prompt_nums else 0), dist, value)
        for penalty, dist, value in raw_candidates
    ]
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def evaluate_numeric_response(
    response: str, raw_spec: str | None, prompt: str | None = None
) -> NumericAuditResult:
    """Evaluate all numeric targets in a question against a model response."""
    specs = parse_numeric_specs(raw_spec)
    if not specs:
        return NumericAuditResult(passed=True, error_type=None, details=[])

    failures: list[str] = []
    for spec in specs:
        extracted = extract_metric_value(response, spec.metric, spec.unit, prompt=prompt)
        if extracted is None:
            failures.append(f"{spec.metric}: missing numeric value (expected {spec.low}..{spec.high})")
        elif not (spec.low - 1e-9 <= extracted <= spec.high + 1e-9):
            failures.append(f"{spec.metric}: got {extracted}, expected {spec.low}..{spec.high}")

    if failures:
        return NumericAuditResult(passed=False, error_type="numeric_error", details=failures)
    return NumericAuditResult(passed=True, error_type=None, details=[])
