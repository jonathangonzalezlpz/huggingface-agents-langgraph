"""Explicit output constraints and deterministic presentation of candidate answers."""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class AnswerContract:
    """Mechanically identifiable requirements, independent of answer correctness."""

    comma_list: bool = False
    order: str | None = None
    decimal_places: int | None = None

    @classmethod
    def from_question(cls, question: str) -> "AnswerContract":
        comma_list = bool(
            re.search(r"comma[ -](?:separated|delimited)", question, re.I)
        )
        order = None
        if comma_list and re.search(r"alphabeti", question, re.I):
            order = "alphabetical"
        elif comma_list and re.search(r"ascending order", question, re.I):
            order = "numeric"
        precision = re.search(r"\b(\d+|two) decimal places\b", question, re.I)
        decimals = None
        if precision:
            decimals = 2 if precision[1].lower() == "two" else int(precision[1])
            if decimals > 12:
                decimals = None
        return cls(comma_list=comma_list, order=order, decimal_places=decimals)

    def present(self, answer: str) -> str:
        """Apply only ordering and precision explicitly required by the question."""
        answer = answer.strip()
        if self.comma_list and "\n" not in answer:
            items = [item.strip() for item in answer.split(",")]
            if self.order == "alphabetical":
                items.sort(key=str.casefold)
            elif self.order == "numeric":
                try:
                    numbers = [Decimal(item) for item in items]
                    if all(number.is_finite() for number in numbers):
                        items = [
                            item for _, item in sorted(zip(numbers, items, strict=True))
                        ]
                except InvalidOperation:
                    pass
            answer = ", ".join(items)
        if self.decimal_places is not None and re.fullmatch(
            r"[-+]?\d+(?:\.\d+)?", answer
        ):
            answer = f"{Decimal(answer):.{self.decimal_places}f}"
        return answer
