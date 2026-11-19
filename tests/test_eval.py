from pathlib import Path

from llm_engineer.eval import evaluate_directory


def test_full_fixture_eval_has_ten_cases_and_no_false_fills():
    report = evaluate_directory(Path(__file__).parents[1] / "data")
    assert report["case_count"] == 10
    assert report["hallucinations"] == 0
    assert report["omissions"] == 0
    assert all(score == 1.0 for score in report["accuracy_by_field"].values())
