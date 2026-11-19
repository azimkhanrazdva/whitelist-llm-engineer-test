import re
from datetime import date

from .schema import Currency, DocumentResult, LineItem


MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    "қаңтар": 1, "ақпан": 2, "наурыз": 3, "сәуір": 4, "мамыр": 5, "маусым": 6,
    "шілде": 7, "тамыз": 8, "қыркүйек": 9, "қазан": 10, "қараша": 11, "желтоқсан": 12,
}
NUMBER_WORDS = {
    "ноль": 0, "нуль": 0, "сто": 100, "двести": 200, "триста": 300, "четыреста": 400,
    "пятьсот": 500, "шестьсот": 600, "семьсот": 700, "восемьсот": 800, "девятьсот": 900,
    "тысяча": 1000, "тысяч": 1000, "тысячи": 1000, "миллион": 1000000,
    "миллиона": 1000000, "миллионов": 1000000, "тридцать": 30, "сорок": 40,
    "үш": 3, "жүз": 100, "қырық": 40, "мың": 1000,
    "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80,
    "девяносто": 90, "двадцать": 20, "десять": 10, "один": 1, "одна": 1,
    "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6,
    "семь": 7, "восемь": 8, "девять": 9, "одиннадцать": 11, "двенадцать": 12,
    "тринадцать": 13, "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16,
    "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19,
}


def _number(value: str) -> float | None:
    cleaned = value.strip().replace("\u00a0", " ")
    cleaned = re.sub(r"[^0-9,.-]", "", cleaned.replace(" ", ""))
    if not cleaned or cleaned in {"-", ".", ","}:
        return None
    if "," in cleaned and "." not in cleaned:
        parts = cleaned.split(",")
        cleaned = "".join(parts) if len(parts[-1]) == 3 else ".".join(parts)
    try:
        number = float(cleaned)
        return int(number) if number.is_integer() else number
    except ValueError:
        return None


def _words_amount(text: str) -> int | None:
    tokens = re.findall(r"[\w]+", text.lower(), flags=re.UNICODE)
    if not tokens or not any(token in NUMBER_WORDS for token in tokens):
        return None
    total = 0
    current = 0
    for token in tokens:
        value = NUMBER_WORDS.get(token)
        if value is None:
            continue
        if value == 100:
            current = (current or 1) * value
        elif value in (1000, 1000000):
            total += (current or 1) * value
            current = 0
        else:
            current += value
    result = total + current
    return result if result > 0 else None


def _date_candidates(text: str) -> list[date]:
    found = []
    for day, month, year in re.findall(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b", text):
        found.append(date(int(year), int(month), int(day)))
    for day, month, year in re.findall(r"\b(\d{1,2})\s+([а-яёәіңғүұқөһ]+)\s+(20\d{2})", text.lower()):
        if month in MONTHS:
            found.append(date(int(year), MONTHS[month], int(day)))
    return found


def _doc_date(text: str, warnings: list[str]) -> date | None:
    candidates = _date_candidates(text)
    unique = list(dict.fromkeys(candidates))
    if len(unique) > 1:
        warnings.append("Multiple document dates found; selected the first explicit date.")
    return unique[0] if unique else None


def _supplier_name(lines: list[str]) -> str | None:
    for line in lines[:8]:
        if re.search(r"\b(ТОО|ИП|ЖШС|LLP|АО)\b|компани[яи]|company", line, re.I):
            line = re.sub(r"^(от\s+)?компани[яи]\s*", "", line, flags=re.I)
            line = re.sub(r"^from\s+company\s*", "", line, flags=re.I).strip()
            line = re.sub(r"^поставщик\s*:\s*", "", line, flags=re.I).strip()
            if line.startswith("«") and line.endswith("»"):
                line = line[1:-1]
            elif line.startswith('"') and line.endswith('"'):
                line = line[1:-1]
            return line or None
    return None


def _bin(text: str, warnings: list[str]) -> str | None:
    match = re.search(r"(?:БИН|БСН|BIN)(?:\s*/\s*(?:БИН|БСН))?\s*[:№.]?\s*([0-9A-Za-zА-Яа-я]{12})", text, re.I)
    if not match:
        return None
    raw = match.group(1)
    if raw.isdigit():
        return raw
    warnings.append(f"BIN candidate '{raw}' contains non-digit OCR characters; left null.")
    return None


def _currency(text: str) -> Currency | None:
    if re.search(r"\b(KZT|тенге|теңге|тг)\b|₸", text, re.I):
        return Currency.KZT
    if re.search(r"\b(USD|доллар)\b|\$", text, re.I):
        return Currency.USD
    if re.search(r"\b(EUR|евро)\b|€", text, re.I):
        return Currency.EUR
    return None


def _totals(text: str, warnings: list[str]) -> tuple[float | None, float | None]:
    labelled = []
    for label in (r"всего\s+к\s+оплате", r"итого", r"общая\s+сумма", r"жалпы\s+сомасы", r"барлығы", r"total"):
        for match in re.finditer(label + r"\s*[:№-]?\s*([0-9][0-9\s.,]*)", text, re.I):
            amount = _number(match.group(1))
            if amount is not None:
                labelled.append((match.start(), label, amount))
    if not labelled:
        words = re.search(r"(?:сумма|сомасы)\s*[:\-]?\s*([\w\s-]+?)(?:\s+00\s+тиын)?(?:\.|$)", text, re.I)
        return (_words_amount(words.group(1)) if words else None), None
    amounts = [entry[2] for entry in labelled]
    if len(set(amounts)) > 1:
        warnings.append("Multiple different total amounts found; selected 'всего к оплате' when present, otherwise the first total.")
    payable = next((x[2] for x in labelled if "всего" in x[1].lower()), labelled[0][2])
    vat = None
    vat_match = re.search(r"НДС(?:\s*\d+(?:[.,]\d+)?\s*%)?\s*[:№-]?\s*([0-9][0-9\s.,]*)", text, re.I)
    if vat_match:
        vat = _number(vat_match.group(1))
    elif re.search(r"НДС[^\n]*(?:не\s+облагается|жоқ|не облагается)", text, re.I):
        warnings.append("VAT is explicitly not charged; vat_amount left null.")
    return payable, vat


def _items(lines: list[str]) -> list[LineItem]:
    items = []
    for line in lines:
        stripped = line.strip(" -•")
        match = re.match(r"(.+?)\s*[—-]\s*(\d+(?:[.,]\d+)?)\s*(?:ед\.?|шт\.?)?\s*[—-]\s*([0-9][0-9\s.,]*)\s*(?:тг|₸|KZT|USD|EUR)?\s*$", stripped, re.I)
        if match:
            items.append(LineItem(name=match.group(1).strip(), qty=_number(match.group(2)), price=_number(match.group(3))))
            continue
        match = re.match(r"(.+?)\s*[—-]\s*([0-9][0-9\s.,]*)\s*(?:тг|₸|KZT|USD|EUR)?\s*$", stripped, re.I)
        if match:
            items.append(LineItem(name=match.group(1).strip(), qty=None, price=_number(match.group(2))))
            continue
        match = re.match(r"(.+?)\s{2,}(\d+(?:[.,]\d+)?)\s+([0-9][0-9 ]*?)\s{2,}[0-9][0-9\s.,]*$", stripped)
        if match:
            items.append(LineItem(name=match.group(1).strip(), qty=_number(match.group(2)), price=_number(match.group(3))))
    return items


def extract_document(text: str) -> DocumentResult:
    if not text or not text.strip():
        return DocumentResult(warnings=["Input document is empty."])
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lower = text.lower()
    warnings: list[str] = []
    if re.search(r"коммерческое\s+предложение|commercial\s+offer", lower):
        doc_type = "commercial_offer"
    elif re.search(r"акт|шот-фактура|оказание\s+услуг", lower):
        doc_type = "act"
    elif re.search(r"сч[её]т|шот|invoice", lower):
        doc_type = "invoice"
    else:
        doc_type = "unknown"
    supplier = _supplier_name(lines)
    supplier_bin = _bin(text, warnings)
    number_match = re.search(r"(?:№|\bno(?:\.|\b)|\bномер\b)\s*([A-Za-zА-Яа-я0-9/-]+)", text, re.I)
    doc_number = number_match.group(1) if number_match else None
    doc_date = _doc_date(text, warnings)
    total, vat = _totals(text, warnings)
    currency = _currency(text)
    if total is not None and currency is None:
        warnings.append("Amount found without an explicit currency; currency left null.")
    result = DocumentResult(
        doc_type=doc_type,
        supplier_name=supplier,
        supplier_bin=supplier_bin,
        doc_number=doc_number,
        doc_date=doc_date,
        currency=currency,
        total_amount=total,
        vat_amount=vat,
        line_items=_items(lines),
        warnings=warnings,
    )
    confidence = {}
    for field in ("doc_type", "supplier_name", "supplier_bin", "doc_number", "doc_date", "currency", "total_amount", "vat_amount", "line_items"):
        value = getattr(result, field)
        confidence[field] = 0.0 if value is None or value == [] or value == "unknown" else (0.98 if field == "supplier_bin" else 0.9)
    result.field_confidence = confidence
    return result
