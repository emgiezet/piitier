"""NER inference, BIO tag utilities, span decoder, and windowed predictor."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

from piitier.labels import Label
from piitier.spans import Span

if TYPE_CHECKING:
    pass

BIO_O: str = "O"


def bio_tag_names() -> list[str]:
    """Return list of all BIO tag names: ['O'] + B-/I- for each Label in enum order."""
    names = [BIO_O]
    for lbl in Label:
        names.append(f"B-{lbl.name}")
        names.append(f"I-{lbl.name}")
    return names


def spans_to_token_labels(spans: list[Span], offset_mapping: list[tuple[int, int]]) -> list[int]:
    """Compute BIO tag IDs for tokens based on ground-truth spans and token offset mapping."""
    tag_names = bio_tag_names()
    tag_to_id = {name: i for i, name in enumerate(tag_names)}
    o_id = tag_to_id[BIO_O]

    labels = [o_id] * len(offset_mapping)
    span_started = {id(s): False for s in spans}
    sorted_spans = sorted(spans, key=lambda s: (s.start, s.end))

    for i, (tok_start, tok_end) in enumerate(offset_mapping):
        if tok_start == 0 and tok_end == 0:
            continue
        if tok_start >= tok_end:
            continue

        matching_span: Span | None = None
        for s in sorted_spans:
            if s.start <= tok_start and tok_end <= s.end:
                matching_span = s
                break

        if matching_span is not None:
            s_id = id(matching_span)
            if not span_started[s_id]:
                tag_name = f"B-{matching_span.label.name}"
                span_started[s_id] = True
            else:
                tag_name = f"I-{matching_span.label.name}"
            labels[i] = tag_to_id.get(tag_name, o_id)

    return labels


def decode_spans(
    text: str,
    offset_mapping: list[tuple[int, int]],
    probs: list[list[float]],
    id2label: dict[int, str],
    threshold: float = 0.0,
) -> list[Span]:
    """Decode token probability distributions into entity Spans."""
    spans: list[Span] = []

    current_label: str | None = None
    current_start: int | None = None
    current_end: int | None = None
    current_scores: list[float] = []

    def flush_entity() -> None:
        nonlocal current_label, current_start, current_end, current_scores
        if current_label is not None and current_start is not None and current_end is not None:
            if current_scores:
                score = sum(current_scores) / len(current_scores)
            else:
                score = 0.0

            if score >= threshold:
                try:
                    label_enum = Label[current_label]
                    spans.append(
                        Span(
                            start=current_start,
                            end=current_end,
                            label=label_enum,
                            source="model:ner",
                            score=float(score),
                            status="valid",
                        )
                    )
                except KeyError:
                    pass

        current_label = None
        current_start = None
        current_end = None
        current_scores = []

    for (tok_start, tok_end), token_probs in zip(offset_mapping, probs):
        if tok_start == 0 and tok_end == 0:
            continue
        if tok_start >= tok_end:
            continue
        if not token_probs:
            flush_entity()
            continue

        best_id = max(range(len(token_probs)), key=lambda idx: token_probs[idx])
        score = token_probs[best_id]
        tag = id2label.get(best_id, BIO_O)

        if tag == BIO_O:
            flush_entity()
        elif tag.startswith("B-"):
            flush_entity()
            lbl_name = tag.removeprefix("B-")
            current_label = lbl_name
            current_start = tok_start
            current_end = tok_end
            current_scores = [score]
        elif tag.startswith("I-"):
            lbl_name = tag.removeprefix("I-")
            if current_label == lbl_name:
                current_end = tok_end
                current_scores.append(score)
            else:
                flush_entity()
        else:
            flush_entity()

    flush_entity()

    spans.sort(key=lambda s: (s.start, s.end))
    return spans


def merge_windows(spans: list[Span]) -> list[Span]:
    """Merge overlapping spans from sliding windows."""
    if not spans:
        return []

    sorted_spans = sorted(spans, key=lambda s: (s.start, s.end, -s.score))
    merged_same: list[Span] = []
    for s in sorted_spans:
        if not merged_same:
            merged_same.append(s)
        else:
            last = merged_same[-1]
            if last.label == s.label and s.start <= last.end:
                new_start = min(last.start, s.start)
                new_end = max(last.end, s.end)
                new_score = max(last.score, s.score)
                merged_same[-1] = Span(
                    start=new_start,
                    end=new_end,
                    label=last.label,
                    source=last.source,
                    score=new_score,
                    status=last.status,
                )
            else:
                merged_same.append(s)

    candidates = sorted(merged_same, key=lambda s: (-s.score, s.start))
    final_spans: list[Span] = []
    for s in candidates:
        overlaps = False
        for fs in final_spans:
            if max(s.start, fs.start) < min(s.end, fs.end):
                overlaps = True
                break
        if not overlaps:
            final_spans.append(s)

    final_spans.sort(key=lambda s: (s.start, s.end))
    return final_spans


class NerPredictor:
    """Sliding-window NER predictor wrapping Hugging Face token classification models."""

    def __init__(
        self,
        checkpoint: str | Path,
        threshold: float = 0.0,
        device: str = "cpu",
        window: int = 512,
        stride: int = 256,
    ) -> None:
        if stride >= window:
            raise ValueError(f"stride ({stride}) must be less than window ({window})")

        if (
            importlib.util.find_spec("torch") is None
            or importlib.util.find_spec("transformers") is None
        ):
            msg = (
                "transformers and torch are required for NerPredictor. "
                "Run `uv sync` to install dependencies."
            )
            raise ImportError(msg)

        import torch
        from transformers import AutoModelForTokenClassification, AutoTokenizer

        _ = torch

        self.threshold = threshold
        self.device = device
        self.window = window
        self.stride = stride

        self.tokenizer = AutoTokenizer.from_pretrained(checkpoint)
        self.model = AutoModelForTokenClassification.from_pretrained(checkpoint)
        self.model.to(device)
        self.model.eval()

        raw_id2label = self.model.config.id2label
        if raw_id2label:
            self.id2label = {int(k): str(v) for k, v in raw_id2label.items()}
        else:
            tag_names = bio_tag_names()
            self.id2label = {i: name for i, name in enumerate(tag_names)}

    def predict(self, text: str) -> list[Span]:
        """Predict PII spans in text using sliding windows."""
        if not text:
            return []

        import torch

        encoding = self.tokenizer(
            text,
            return_offsets_mapping=True,
            return_overflowing_tokens=True,
            max_length=self.window,
            stride=self.stride,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )

        input_ids = encoding["input_ids"].to(self.device)
        attention_mask = encoding["attention_mask"].to(self.device)
        offset_mappings = encoding["offset_mapping"].tolist()

        with torch.no_grad():
            outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1).cpu().tolist()

        all_spans: list[Span] = []
        for w in range(len(offset_mappings)):
            window_spans = decode_spans(
                text=text,
                offset_mapping=offset_mappings[w],
                probs=probs[w],
                id2label=self.id2label,
                threshold=self.threshold,
            )
            all_spans.extend(window_spans)

        return merge_windows(all_spans)
