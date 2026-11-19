from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentType(str, Enum):
    invoice = "invoice"
    commercial_offer = "commercial_offer"
    act = "act"
    unknown = "unknown"


class Currency(str, Enum):
    KZT = "KZT"
    USD = "USD"
    EUR = "EUR"


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    qty: float | None = None
    price: float | None = None


class DocumentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_type: DocumentType = DocumentType.unknown
    supplier_name: str | None = None
    supplier_bin: str | None = None
    doc_number: str | None = None
    doc_date: date | None = None
    currency: Currency | None = None
    total_amount: float | None = None
    vat_amount: float | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    field_confidence: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("supplier_bin")
    @classmethod
    def validate_bin(cls, value):
        if value is not None and (len(value) != 12 or not value.isdigit()):
            raise ValueError("supplier_bin must contain exactly 12 digits")
        return value

    @field_validator("field_confidence")
    @classmethod
    def validate_confidence(cls, value):
        for field, score in value.items():
            if not 0 <= score <= 1:
                raise ValueError(f"confidence for {field} must be between 0 and 1")
        return value


def null_result(**updates: Any) -> DocumentResult:
    """Create a schema-valid empty result, keeping absent values explicit."""
    return DocumentResult(**updates)
