import json
from pathlib import Path
from typing import Any

from .extractor import extract_document

FIELDS = [
    "doc_type", "supplier_name", "supplier_bin", "doc_number", "doc_date", "currency",
    "total_amount", "vat_amount", "line_items",
]


def _normal(value: Any):
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def compare_case(actual: dict, expected: dict) -> dict:
    field_report = {}
    hallucinations = 0
    omissions = 0
    for field in FIELDS:
        got = _normal(actual.get(field))
        want = _normal(expected.get(field))
        correct = got == want
        is_hallucination = got is not None and want is None
        is_omission = got is None and want is not None
        hallucinations += int(is_hallucination)
        omissions += int(is_omission)
        field_report[field] = {
            "correct": correct,
            "expected": want,
            "actual": got,
            "hallucination": is_hallucination,
            "omission": is_omission,
        }
    return {"fields": field_report, "hallucinations": hallucinations, "omissions": omissions}


def evaluate_directory(data_dir: str | Path) -> dict:
    root = Path(data_dir)
    cases = []
    for expected_path in sorted(root.glob("*.json")):
        text_path = expected_path.with_suffix(".txt")
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        actual = extract_document(text_path.read_text(encoding="utf-8")).model_dump(mode="json")
        cases.append({"name": expected_path.stem, **compare_case(actual, expected)})
    accuracy = {}
    for field in FIELDS:
        accuracy[field] = sum(case["fields"][field]["correct"] for case in cases) / len(cases) if cases else 0
    return {
        "cases": cases,
        "case_count": len(cases),
        "accuracy_by_field": accuracy,
        "hallucinations": sum(case["hallucinations"] for case in cases),
        "omissions": sum(case["omissions"] for case in cases),
    }
