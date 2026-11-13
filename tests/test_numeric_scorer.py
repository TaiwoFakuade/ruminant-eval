from src.ruminant_eval.evaluator import classify_error, score_response
from src.ruminant_eval.numeric_scorer import evaluate_numeric_response


def test_q07_crude_protein_catches_wrong_factor():
    b_resp = "A feed with 2.4% nitrogen has 12% crude protein, because CP = N × 5.0."
    a_resp = "Multiplying 2.4% nitrogen by the standard 6.25 factor gives 15.0% crude protein."
    assert not evaluate_numeric_response(b_resp, "cp=15.0±0.1[%]").passed
    assert evaluate_numeric_response(a_resp, "cp=15.0±0.1[%]").passed


def test_q08_fcr_catches_arithmetic_error_and_ignores_prompt_inputs():
    b_resp = "Feed intake is 9 kg/day and weight gain is 1.5 kg/day, so feed conversion ratio is 4.5 — lower is better."
    a_resp = "Feed conversion ratio (FCR) is intake divided by gain: 9 kg ÷ 1.5 kg = 6.0."
    res_b = evaluate_numeric_response(b_resp, "fcr=6.0±0.05[]")
    assert not res_b.passed
    assert res_b.error_type == "numeric_error"
    assert evaluate_numeric_response(a_resp, "fcr=6.0±0.05[]").passed


def test_q09_multi_target_cp_and_water():
    b_resp = "A Holstein in peak lactation giving 35 L/day needs only 12% CP and about 20 L of water a day."
    a_resp = "A peak Holstein producing 35 L/day requires 17% CP and roughly 115 L of water daily."
    res_b = evaluate_numeric_response(b_resp, "cp=16-18[%]; water=100-130[L]")
    assert not res_b.passed
    assert len(res_b.details) == 2
    assert evaluate_numeric_response(a_resp, "cp=16-18[%]; water=100-130[L]").passed


def test_q14_far_off_dry_cow_cp():
    b_resp = "Give a far-off dry cow the same high-energy lactating ration every day, about 18% CP."
    a_resp = "A far-off dry cow needs maintenance energy and around 11.5% CP."
    assert not evaluate_numeric_response(b_resp, "cp=11-12[%]").passed
    assert evaluate_numeric_response(a_resp, "cp=11-12[%]").passed


def test_q08_score_drops_from_80_to_50_with_numeric_penalty():
    b_resp = "Feed intake is 9 kg/day and weight gain is 1.5 kg/day, so feed conversion ratio is 4.5 — lower is better."
    keywords = ["feed conversion ratio", "feed intake", "weight gain", "lower", "6.0"]
    assert score_response(b_resp, keywords, "fcr=6.0±0.05[]") == 50.0
    assert classify_error(b_resp, keywords, "fcr=6.0±0.05[]") == "numeric_error"


def test_no_numeric_spec_means_no_penalty():
    assert evaluate_numeric_response("Any text", "").passed
    assert evaluate_numeric_response("Any text", None).passed


def test_prompt_numbers_are_deprioritised():
    # A model echoing the prompt ("For a 650 kg cow...") must not have
    # the echoed 650 kg mistaken for the answer.
    prompt = "Estimate daily dry matter intake (DMI) for a 650 kg lactating Holstein consuming 3.6% of body weight in DM."
    echoed = "For a 650 kg cow consuming 3.6% BW, DMI is 23.4 kg."
    assert evaluate_numeric_response(echoed, "dmi=23.4±0.2[kg]", prompt).passed
    # Without the prompt, the same extraction still works.
    assert evaluate_numeric_response(echoed, "dmi=23.4±0.2[kg]").passed


def test_refuted_number_is_not_picked_up():
    # Strong models explain why the common mistake is wrong first.
    # The refuted distractor sits closer to the alias but must lose.
    assert evaluate_numeric_response(
        "Rather than 12.0%, the true crude protein is 15.0%",
        "cp=15.0±0.1[%]",
    ).passed
    assert evaluate_numeric_response(
        "Not 4.5 — feed conversion ratio is 6.0",
        "fcr=6.0±0.05[]",
    ).passed
