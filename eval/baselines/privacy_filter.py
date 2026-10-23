"""OpenAI Privacy Filter baseline system with BILOU decoding."""

from __future__ import annotations

from typing import TYPE_CHECKING

from piitier.labels import Label
from piitier.spans import Span

if TYPE_CHECKING:
    from piitier.ner.inference import NerPredictor

PRIVACY_FILTER_LABEL_MAP: dict[str, Label] = {
    "private_person": Label.OSOBA,
    "private_address": Label.ADRES,
    "private_date": Label.DATA_URODZENIA,
    "private_email": Label.EMAIL,
    "private_phone": Label.TELEFON,
    "account_number": Label.NR_RACHUNKU,
}


def decode_bilou(
    offset_mapping: list[tuple[int, int]],
    probs: list[list[float]],
    id2label: dict[int, str],
) -> list[tuple[int, int, str, float]]:
    """Decode BILOU token probability distributions into entity spans (start, end, type, score)."""
    spans: list[tuple[int, int, str, float]] = []

    current_type: str | None = None
    current_start: int | None = None
    current_end: int | None = None
    current_scores: list[float] = []

    def flush() -> None:
        nonlocal current_type, current_start, current_end, current_scores
        if current_type is not None and current_start is not None and current_end is not None:
            if current_scores:
                score = sum(current_scores) / len(current_scores)
            else:
                score = 0.0
            spans.append((current_start, current_end, current_type, float(score)))
        current_type = None
        current_start = None
        current_end = None
        current_scores = []

    for (tok_start, tok_end), token_probs in zip(offset_mapping, probs):
        if tok_start == 0 and tok_end == 0:
            continue
        if tok_start >= tok_end:
            continue
        if not token_probs:
            flush()
            continue

        best_id = max(range(len(token_probs)), key=lambda idx: token_probs[idx])
        score = token_probs[best_id]
        tag = id2label.get(best_id, "O")

        if tag == "O":
            flush()
        elif tag.startswith("S-"):
            flush()
            ent_type = tag.removeprefix("S-")
            spans.append((tok_start, tok_end, ent_type, float(score)))
        elif tag.startswith("B-"):
            flush()
            ent_type = tag.removeprefix("B-")
            current_type = ent_type
            current_start = tok_start
            current_end = tok_end
            current_scores = [score]
        elif tag.startswith("I-"):
            ent_type = tag.removeprefix("I-")
            if current_type == ent_type and current_start is not None:
                current_end = tok_end
                current_scores.append(score)
            else:
                flush()
        elif tag.startswith("L-"):
            ent_type = tag.removeprefix("L-")
            if current_type == ent_type and current_start is not None:
                current_end = tok_end
                current_scores.append(score)
                flush()
            else:
                flush()
        else:
            flush()

    flush()
    spans.sort(key=lambda s: (s[0], s[1]))
    return spans


class PrivacyFilterSystem:
    """OpenAI Privacy Filter baseline system."""

    name: str = "privacy-filter"

    def __init__(self, threshold: float = 0.0, device: str = "cpu", **kwargs: object) -> None:
        self.threshold = threshold
        self.device = device
        self._predictor: NerPredictor | None = None

    @property
    def unmapped(self) -> frozenset[Label]:
        return frozenset(lbl for lbl in Label if lbl not in PRIVACY_FILTER_LABEL_MAP.values())

    def _init_predictor(self) -> None:
        if self._predictor is not None:
            return

        from piitier.ner.inference import NerPredictor

        self._predictor = NerPredictor(
            checkpoint="openai/privacy-filter",
            threshold=self.threshold,
            device=self.device,
        )

    def predict(self, text: str) -> list[Span]:
        """Predict PII spans using privacy-filter model with BILOU decoding."""
        if not text:
            return []
        self._init_predictor()
        predictor = self._predictor
        assert predictor is not None

        import torch

        encoding = predictor.tokenizer(
            text,
            return_offsets_mapping=True,
            return_overflowing_tokens=True,
            max_length=predictor.window,
            stride=predictor.stride,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )

        input_ids = encoding["input_ids"].to(predictor.device)
        attention_mask = encoding["attention_mask"].to(predictor.device)
        offset_mappings = encoding["offset_mapping"].tolist()

        with torch.no_grad():
            outputs = predictor.model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1).cpu().tolist()

        all_spans: list[Span] = []
        for w in range(len(offset_mappings)):
            raw_tuples = decode_bilou(
                offset_mapping=offset_mappings[w],
                probs=probs[w],
                id2label=predictor.id2label,
            )
            for start, end, raw_type, score in raw_tuples:
                if score >= self.threshold:
                    label = PRIVACY_FILTER_LABEL_MAP.get(raw_type)
                    if label is not None:
                        try:
                            all_spans.append(
                                Span(
                                    start=start,
                                    end=end,
                                    label=label,
                                    source="baseline:privacy-filter",
                                    score=score,
                                    status="valid",
                                )
                            )
                        except ValueError:
                            pass

        from piitier.ner.inference import merge_windows

        return merge_windows(all_spans)
