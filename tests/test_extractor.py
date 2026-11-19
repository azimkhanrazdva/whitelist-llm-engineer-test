import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from llm_engineer.extractor import extract_document
from llm_engineer.schema import DocumentResult


FIXTURES = Path(__file__).parents[1] / "data"


def load_case(name):
    text = (FIXTURES / f"{name}.txt").read_text(encoding="utf-8")
    expected = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return text, expected


def test_invoice_extracts_explicit_fields_and_final_payable_total():
    text, _ = load_case("01_invoice")
    result = extract_document(text).model_dump()
    assert result["doc_type"] == "invoice"
    assert result["supplier_bin"] == "170340021554"
    assert result["total_amount"] == 186180
    assert result["vat_amount"] == 25680
    assert result["warnings"]


def test_missing_values_are_null_and_never_guessed():
    text, _ = load_case("04_missing_fields")
    result = extract_document(text).model_dump()
    assert result["supplier_bin"] is None
    assert result["doc_date"] is None
    assert result["vat_amount"] is None
    assert result["total_amount"] == 12500


def test_ocr_bin_is_rejected_and_reported():
    text, _ = load_case("03_ocr_kz")
    result = extract_document(text).model_dump()
    assert result["supplier_bin"] is None
    assert any("BIN" in warning or "БИН" in warning for warning in result["warnings"])


def test_words_amount_is_converted_only_when_unambiguous():
    text, _ = load_case("05_words_amount")
    result = extract_document(text).model_dump()
    assert result["total_amount"] == 340000
    assert result["currency"] == "KZT"


def test_schema_rejects_invalid_bin_and_currency():
    with pytest.raises(ValidationError):
        DocumentResult(supplier_bin="123", currency="RUB")


def test_eval_counts_accuracy_hallucinations_and_omissions():
    from llm_engineer.eval import compare_case

    _, expected = load_case("04_missing_fields")
    actual = extract_document((FIXTURES / "04_missing_fields.txt").read_text(encoding="utf-8")).model_dump()
    report = compare_case(actual, expected)
    assert report["fields"]["supplier_bin"]["correct"] is True
    assert report["hallucinations"] == 0
    assert report["omissions"] == 0


def test_model_output_is_validated_before_it_can_be_returned():
    from llm_engineer.llm import OllamaClient

    client = OllamaClient()
    client.endpoint = "http://127.0.0.1:1/does-not-exist"
    with pytest.raises(RuntimeError, match="Ollama is unavailable"):
        client.extract("test")
