from types import SimpleNamespace

import pytest

from src.ask_data import (
    Evidence, UnsafeAnswerError, _validate_answer, ask_data, build_evidence_store, retrieve_evidence,
)


class FakeResponses:
    def __init__(self, answer):
        self.answer = answer
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(output_text=self.answer)


class SequencedResponses:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=next(self.answers))


class FakeClient:
    def __init__(self, answer):
        self.responses = FakeResponses(answer)


def test_public_evidence_store_and_targeted_retrieval():
    evidence = build_evidence_store(__import__("pathlib").Path("data/published"))
    selected = retrieve_evidence("What is the mean income for Black women age 25–34 in Texas in 2024?", evidence)
    assert selected
    assert "Texas" in selected[0].text
    assert "Black women" in selected[0].text
    assert "25–34" in selected[0].text
    assert selected[0].metric == "mean_personal_income"


def test_broad_trend_defaults_to_all_ages_and_model_terms_route_to_models():
    evidence = build_evidence_store(__import__("pathlib").Path("data/published"))
    trends = retrieve_evidence("How did national employment for Black women change from 2022 to 2024?", evidence)
    assert trends[0].source == "trends.csv"
    assert "Black women | All ages" in trends[0].text
    models = retrieve_evidence("What is the 2024 model Brier score?", evidence)
    assert models[0].source == "model_metrics.csv"
    assert models[0].metric == "brier_score"
    assert "overall=All Black adults" in models[0].text


def test_specific_metric_outranks_generic_population_language():
    evidence = build_evidence_store(__import__("pathlib").Path("data/published"))
    selected = retrieve_evidence(
        "What is the 2024 national marriage rate for all Black adults?", evidence
    )
    assert selected[0].metric == "married_rate"
    assert selected[0].source == "national.csv"
    assert "Marriage rate: 32.0%" in selected[0].text


def test_inference_questions_route_to_age_adjusted_evidence():
    evidence = (
        Evidence("national.csv", "married_rate", "2024 national marriage rate 32.0%", "2024 national marriage rate", 0.32, False),
        Evidence(
            "inference.csv", "married_rate",
            "2024 National age-adjusted marriage difference -4.0%; q-value 0.01",
            "2024 national age adjusted marriage difference significant reliable q value",
            -0.04, False,
        ),
    )
    selected = retrieve_evidence(
        "Is the age-adjusted national marriage difference statistically significant?", evidence
    )
    assert selected[0].source == "inference.csv"


def test_api_request_is_not_stored_and_uses_aggregate_packet():
    evidence = (
        Evidence("national.csv", "married_rate", "2024 | National | Marriage rate: 32.0% [public aggregate].", "2024 national marriage rate", 0.32, False),
    )
    client = FakeClient("The published national marriage rate is 32.0% [E1].")
    result = ask_data("What is the national marriage rate?", evidence, client, "test-model")
    assert result.text.endswith("[E1].")
    assert client.responses.kwargs["store"] is False
    assert client.responses.kwargs["max_output_tokens"] == 500
    assert "32.0%" in client.responses.kwargs["input"][-1]["content"]


def test_generated_numbers_must_exist_in_evidence():
    evidence = (
        Evidence("national.csv", "married_rate", "2024 | National | Marriage rate: 32.0%.", "2024 national marriage rate", 0.32, False),
    )
    with pytest.raises(UnsafeAnswerError, match="unsupported numeric"):
        _validate_answer("It is 99.0% [E1].", evidence)


def test_equivalent_numeric_formatting_is_accepted_without_weakening_units():
    evidence = (
        Evidence("national.csv", "married_rate", "2024 | National | Marriage rate: 32.0%.", "2024 national marriage rate", 0.32, False),
    )
    result = ask_data("What is the rate?", evidence, FakeClient("In 2024, it was 32% [E1]."), "test-model")
    assert result.text == "In 2024, it was 32% [E1]."
    with pytest.raises(UnsafeAnswerError, match="unsupported numeric"):
        _validate_answer("In 2024, it was $32 [E1].", evidence)


def test_failed_draft_is_retried_once_with_the_same_evidence_packet():
    evidence = (
        Evidence("national.csv", "married_rate", "2024 | National | Marriage rate: 32.0%.", "2024 national marriage rate", 0.32, False),
    )
    responses = SequencedResponses(("It was 33.0% [E1].", "In 2024, it was 32.0% [E1]."))
    client = SimpleNamespace(responses=responses)
    result = ask_data("What is the 2024 national marriage rate?", evidence, client, "test-model")
    assert result.text == "In 2024, it was 32.0% [E1]."
    assert len(responses.calls) == 2
    assert responses.calls[0]["store"] is False
    assert responses.calls[1]["store"] is False
    assert responses.calls[0]["input"][-1]["content"] == responses.calls[1]["input"][-2]["content"]
    assert "33.0%" not in str(responses.calls[1]["input"])


def test_two_failed_drafts_return_a_validated_verbatim_evidence_fallback():
    evidence = (
        Evidence(
            "national.csv", "married_rate",
            "2024 | National | All Black adults | All ages | Marriage rate: 32.0% (95% CI 31.7%–32.3%).",
            "2024 national marriage rate", 0.32, False,
        ),
    )
    responses = SequencedResponses(("It was 33.0% [E1].", "It was 34.0% [E1]."))
    result = ask_data(
        "What is the 2024 national marriage rate for all Black adults?",
        evidence,
        SimpleNamespace(responses=responses),
        "test-model",
    )
    assert result.text.endswith("32.0% (95% CI 31.7%–32.3%) [E1].")
    assert "33.0%" not in result.text
    assert "34.0%" not in result.text
    assert len(responses.calls) == 2


def test_generated_citations_must_resolve():
    evidence = (
        Evidence("national.csv", "married_rate", "2024 | National | Marriage rate: 32.0%.", "2024 national marriage rate", 0.32, False),
    )
    with pytest.raises(UnsafeAnswerError, match="citations"):
        _validate_answer("The evidence reports the rate [E9].", evidence)


def test_numeric_claim_must_match_the_cited_record():
    evidence = (
        Evidence("states.csv", "married_rate", "2024 | Texas | Marriage rate: 30.0%.", "texas marriage", 0.30, False),
        Evidence("states.csv", "married_rate", "2024 | Georgia | Marriage rate: 40.0%.", "georgia marriage", 0.40, False),
    )
    client = FakeClient("Texas has a marriage rate of 40.0% [E1].")
    with pytest.raises(UnsafeAnswerError, match="cited evidence"):
        _validate_answer(client.responses.answer, evidence)


def test_each_numeric_sentence_requires_its_own_citation():
    evidence = (
        Evidence("states.csv", "married_rate", "2024 | Texas | Marriage rate: 30.0%.", "texas marriage", 0.30, False),
    )
    client = FakeClient("The evidence is from 2024. The marriage rate is 30.0% [E1].")
    with pytest.raises(UnsafeAnswerError, match="did not include"):
        _validate_answer(client.responses.answer, evidence)


def test_question_length_is_bounded():
    evidence = (
        Evidence("national.csv", "married_rate", "National marriage rate.", "national marriage rate", 0.32, False),
    )
    with pytest.raises(ValueError, match="1–500"):
        retrieve_evidence("x" * 501, evidence)


def test_suppressed_record_contains_no_estimate():
    evidence = (
        Evidence(
            "states.csv", "married_rate",
            "2024 | Alaska | Marriage rate: Suppressed; unweighted n 12; weighted denominator 900.",
            "2024 alaska marriage rate suppressed", None, True,
        ),
    )
    selected = retrieve_evidence("What is Alaska's marriage rate?", evidence)
    assert selected[0].suppressed is True
    assert "Suppressed" in selected[0].text
