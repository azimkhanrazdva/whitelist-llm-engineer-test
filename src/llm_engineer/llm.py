import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from pydantic import ValidationError

from .schema import DocumentResult


SYSTEM_PROMPT = """Return only JSON matching this schema. Never infer absent values: use null. line_items must be an array. Put contradictions and OCR uncertainty in warnings. doc_type must be invoice, commercial_offer, act, or unknown; currency must be KZT, USD, EUR, or null.
{"doc_type":"invoice|commercial_offer|act|unknown","supplier_name":"string|null","supplier_bin":"12 digits|null","doc_number":"string|null","doc_date":"YYYY-MM-DD|null","currency":"KZT|USD|EUR|null","total_amount":"number|null","vat_amount":"number|null","line_items":[{"name":"string","qty":"number|null","price":"number|null"}],"field_confidence":{"field":0.0},"warnings":["string"]}"""


@dataclass
class OllamaClient:
    model: str = "llama3.2:3b"
    endpoint: str = "http://127.0.0.1:11434/api/generate"
    timeout: float = 60.0

    def extract(self, text: str) -> DocumentResult:
        payload = json.dumps({
            "model": self.model,
            "prompt": f"{SYSTEM_PROMPT}\n\nDocument:\n{text}",
            "stream": False,
            "format": "json",
        }).encode("utf-8")
        request = urllib.request.Request(self.endpoint, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError) as exc:
            raise RuntimeError("Ollama is unavailable; use the default offline backend or start Ollama locally.") from exc
        raw = body.get("response")
        if not isinstance(raw, str):
            raise ValueError("Ollama response did not contain a JSON string in 'response'.")
        try:
            return DocumentResult.model_validate_json(raw)
        except ValidationError as exc:
            raise ValueError("Ollama returned JSON that failed the document schema validation.") from exc
