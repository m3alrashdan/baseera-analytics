"""Arabic number agreement.

Arabic inflects the counted noun by the number in front of it. Writing "5 صف" or
"1 صفًا" reads as machine output to a native speaker, which is exactly the impression
a product sold into an Arabic-speaking company cannot afford.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Noun:
    """The four forms Arabic counting needs."""

    singular: str  # صف
    dual: str  # صفان
    plural: str  # صفوف
    accusative: str  # صفًا (the تمييز after 11-99)


ROW = Noun("صف", "صفان", "صفوف", "صفًا")
CELL = Noun("خلية", "خليتان", "خلايا", "خلية")
COLUMN = Noun("عمود", "عمودان", "أعمدة", "عمودًا")
STEP = Noun("خطوة", "خطوتان", "خطوات", "خطوة")
VALUE = Noun("قيمة", "قيمتان", "قيم", "قيمة")
MONTH = Noun("شهر", "شهران", "أشهر", "شهرًا")
FINDING = Noun("ملاحظة", "ملاحظتان", "ملاحظات", "ملاحظة")
RECORD = Noun("سجل", "سجلان", "سجلات", "سجلًا")


def count(number: int, noun: Noun) -> str:
    """Render a count with the correct Arabic form.

    0 -> plural, 1 -> bare singular, 2 -> dual, 3-10 -> plural,
    11-99 -> accusative singular, 100+ -> genitive singular.
    """
    number = int(number)
    if number == 0:
        return f"لا {noun.plural}"
    if number == 1:
        feminine = noun.singular[-1] in "ةه"
        return f"{noun.singular} {'واحدة' if feminine else 'واحد'}"
    if number == 2:
        return noun.dual
    remainder = number % 100
    if 3 <= remainder <= 10:
        return f"{number:,} {noun.plural}"
    if 11 <= remainder <= 99:
        return f"{number:,} {noun.accusative}"
    return f"{number:,} {noun.singular}"


def joined(items: list[str]) -> str:
    """Join a list with the Arabic comma, and "و" before the last item."""
    clean = [item for item in items if item]
    if not clean:
        return "—"
    if len(clean) == 1:
        return clean[0]
    return "، ".join(clean[:-1]) + " و" + clean[-1]
