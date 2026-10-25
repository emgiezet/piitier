from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

_config_path = Path(__file__).resolve().parents[2] / "training" / "config.py"
_spec_cfg = importlib.util.spec_from_file_location("training.config", _config_path)
if _spec_cfg is not None and _spec_cfg.loader is not None:
    _config_mod = importlib.util.module_from_spec(_spec_cfg)
    sys.modules["training.config"] = _config_mod
    _spec_cfg.loader.exec_module(_config_mod)

_train_path = Path(__file__).resolve().parents[2] / "training" / "train.py"
_spec = importlib.util.spec_from_file_location("training.train", _train_path)
if _spec is not None and _spec.loader is not None:
    _train_mod = importlib.util.module_from_spec(_spec)
    sys.modules["training.train"] = _train_mod
    _spec.loader.exec_module(_train_mod)

build_dataset = _train_mod.build_dataset
main = _train_mod.main


class TokenizerStub:
    """Mock tokenizer returning deterministic offset mappings and encodings."""

    def __call__(
        self,
        texts: list[str],
        return_offsets_mapping: bool = True,
        truncation: bool = True,
        max_length: int = 128,
        padding: str = "max_length",
    ) -> dict[str, list[list[Any]]]:
        input_ids_batch = []
        attention_mask_batch = []
        offset_mapping_batch = []

        for text in texts:
            tokens = text.split()
            toks = ["[CLS]"] + tokens + ["[SEP]"]
            input_ids = [101] + [100] * len(tokens) + [102]
            attention_mask = [1] * len(toks)

            if len(toks) < max_length:
                pad_len = max_length - len(toks)
                input_ids.extend([0] * pad_len)
                attention_mask.extend([0] * pad_len)
                toks.extend(["[PAD]"] * pad_len)

            offsets = [(0, 0)]
            curr_pos = 0
            for t in tokens:
                start = text.find(t, curr_pos)
                end = start + len(t)
                offsets.append((start, end))
                curr_pos = end
            offsets.append((0, 0))

            if len(offsets) < max_length:
                offsets.extend([(0, 0)] * (max_length - len(offsets)))

            input_ids_batch.append(input_ids[:max_length])
            attention_mask_batch.append(attention_mask[:max_length])
            offset_mapping_batch.append(offsets[:max_length])

        return {
            "input_ids": input_ids_batch,
            "attention_mask": attention_mask_batch,
            "offset_mapping": offset_mapping_batch,
        }


def test_uc73_build_dataset_unit() -> None:
    """UC-73: build_dataset unit test with tokenizer-stub checks BIO labels and structure."""
    tokenizer = TokenizerStub()
    from piitier.ner.inference import bio_tag_names

    bio_tag_names()

    records = [
        {
            "id": "doc_1",
            "doc_type": "polisa",
            "text": "90051512340",
            "spans": [{"start": 0, "end": 11, "label": "PESEL", "text": "90051512340"}],
        }
    ]

    dataset = build_dataset(records, tokenizer, max_length=16)
    assert len(dataset) == 1
    sample = dataset[0]
    assert "input_ids" in sample
    assert "attention_mask" in sample
    assert "labels" in sample
    assert sample["labels"].shape[0] == 16


def test_uc98_build_dataset_leading_space_token_gets_b() -> None:
    """UC-98: build_dataset assigns B- to a BPE token whose leading space precedes span start.

    Regression for the bug where tok_start < span.start caused the first token to be O.
    Uses a fake tokenizer whose offset_mapping includes a leading-space token.
    """
    from piitier.ner.inference import bio_tag_names

    tag_names = bio_tag_names()
    tag_to_id = {n: i for i, n in enumerate(tag_names)}
    b_email = tag_to_id["B-EMAIL"]
    i_email = tag_to_id["I-EMAIL"]
    o_id = tag_to_id["O"]
    IGNORE = -100

    # Text where 'JANINA75' starts at position 7 and BPE gives a leading-space token at 6.
    text = "Email: JANINA75@EXAMPLE.NET"
    # Span covers exactly "JANINA75@EXAMPLE.NET" starting at 7.
    records = [
        {
            "id": "doc_email",
            "doc_type": "test",
            "text": text,
            "spans": [{"start": 7, "end": 27, "label": "EMAIL", "text": "JANINA75@EXAMPLE.NET"}],
        }
    ]

    class LeadingSpaceTokenizerStub:
        """Fake tokenizer that returns one BPE token with a leading space over span start."""

        def __call__(
            self,
            texts: list[str],
            return_offsets_mapping: bool = True,
            truncation: bool = True,
            max_length: int = 128,
            padding: str = "max_length",
        ) -> dict[str, list[list[object]]]:
            results: dict[str, list[list[object]]] = {
                "input_ids": [],
                "attention_mask": [],
                "offset_mapping": [],
            }
            for _ in texts:
                # Hand-crafted offsets: CLS, 'Email:', ' JAN' (leading space!), 'INA75',
                # '@', 'EXAMPLE', '.', 'NET', SEP, then padding.
                offsets: list[tuple[int, int]] = [
                    (0, 0),  # [CLS]
                    (0, 6),  # 'Email:'
                    (6, 10),  # ' JAN'  ← tok_start=6 < span_start=7
                    (10, 15),  # 'INA75'
                    (15, 16),  # '@'
                    (16, 23),  # 'EXAMPLE'
                    (23, 24),  # '.'
                    (24, 27),  # 'NET'
                    (0, 0),  # [SEP]
                ]
                n_real = len(offsets)
                pad = [(0, 0)] * (max_length - n_real)
                results["input_ids"].append(
                    ([101] + [100] * (n_real - 2) + [102] + [0] * len(pad))[:max_length]
                )
                results["attention_mask"].append(([1] * n_real + [0] * len(pad))[:max_length])
                results["offset_mapping"].append((offsets + pad)[:max_length])
            return results

    dataset = build_dataset(records, LeadingSpaceTokenizerStub(), max_length=16)
    assert len(dataset) == 1
    sample = dataset[0]
    labels = sample["labels"].tolist()

    # Indices in the padded sequence:
    # 0 → CLS → IGNORE (-100)
    # 1 → 'Email:' → O
    # 2 → ' JAN' (leading-space token, covers span start at 7) → B-EMAIL
    # 3 → 'INA75' → I-EMAIL
    # 4 → '@' → I-EMAIL
    # 5 → 'EXAMPLE' → I-EMAIL
    # 6 → '.' → I-EMAIL
    # 7 → 'NET' → I-EMAIL
    # 8 → SEP → IGNORE (-100)
    # 9..15 → PAD → IGNORE (-100)
    assert labels[0] == IGNORE, f"CLS should be IGNORE, got {labels[0]}"
    assert labels[1] == o_id, f"'Email:' should be O, got {labels[1]}"
    assert labels[2] == b_email, f"' JAN' (leading-space) should be B-EMAIL, got {labels[2]}"
    assert labels[3] == i_email, f"'INA75' should be I-EMAIL, got {labels[3]}"
    assert labels[4] == i_email, f"'@' should be I-EMAIL, got {labels[4]}"
    assert all(lab == IGNORE for lab in labels[8:]), "padding/SEP should be IGNORE"


def test_uc101_build_dataset_internal_whitespace_token_is_ignore() -> None:
    """UC-101: build_dataset labels a whitespace-only token inside an entity as IGNORE (-100).

    Regression for pii-5-v2: KWOTA "717 253,28" was split because the space token inside
    was labeled O, teaching the model O mid-entity, which then flushed decode_spans.
    """
    from piitier.ner.inference import bio_tag_names

    tag_names = bio_tag_names()
    tag_to_id = {n: i for i, n in enumerate(tag_names)}
    b_kwota = tag_to_id["B-KWOTA"]
    i_kwota = tag_to_id["I-KWOTA"]
    o_id = tag_to_id["O"]
    IGNORE = -100

    # "Kwota: 717 253,28" — KWOTA span covers "717 253,28" at [7, 17).
    text = "Kwota: 717 253,28"
    records = [
        {
            "id": "kwota_test",
            "doc_type": "test",
            "text": text,
            "spans": [{"start": 7, "end": 17, "label": "KWOTA", "text": "717 253,28"}],
        }
    ]

    class KwotaTokenizerStub:
        """Stub that emits a standalone space token between '717' and '253'."""

        def __call__(
            self,
            texts: list[str],
            return_offsets_mapping: bool = True,
            truncation: bool = True,
            max_length: int = 128,
            padding: str = "max_length",
        ) -> dict[str, list[list[object]]]:
            results: dict[str, list[list[object]]] = {
                "input_ids": [],
                "attention_mask": [],
                "offset_mapping": [],
            }
            for _ in texts:
                offsets: list[tuple[int, int]] = [
                    (0, 0),  # [CLS]
                    (0, 7),  # 'Kwota: '
                    (7, 10),  # '717'     — B-KWOTA expected
                    (10, 11),  # ' '       — whitespace-only inside span → IGNORE expected
                    (11, 14),  # '253'     — I-KWOTA expected
                    (14, 15),  # ','       — I-KWOTA expected
                    (15, 17),  # '28'      — I-KWOTA expected
                    (0, 0),  # [SEP]
                ]
                n_real = len(offsets)
                pad = [(0, 0)] * (max_length - n_real)
                results["input_ids"].append(
                    ([101] + [100] * (n_real - 2) + [102] + [0] * len(pad))[:max_length]
                )
                results["attention_mask"].append(([1] * n_real + [0] * len(pad))[:max_length])
                results["offset_mapping"].append((offsets + pad)[:max_length])
            return results

    dataset = build_dataset(records, KwotaTokenizerStub(), max_length=16)
    assert len(dataset) == 1
    labels = dataset[0]["labels"].tolist()

    # idx 0 = CLS → -100 (build_dataset post-process)
    # idx 1 = 'Kwota: ' → O
    # idx 2 = '717' → B-KWOTA
    # idx 3 = ' ' (whitespace inside span) → IGNORE (-100)
    # idx 4 = '253' → I-KWOTA
    # idx 5 = ',' → I-KWOTA
    # idx 6 = '28' → I-KWOTA
    # idx 7 = SEP → -100; idx 8..15 = PAD → -100
    assert labels[0] == IGNORE, f"CLS → IGNORE, got {labels[0]}"
    assert labels[1] == o_id, f"'Kwota: ' → O, got {labels[1]}"
    assert labels[2] == b_kwota, f"'717' → B-KWOTA, got {labels[2]}"
    assert labels[3] == IGNORE, f"' ' inside span → IGNORE, got {labels[3]}"
    assert labels[4] == i_kwota, f"'253' → I-KWOTA, got {labels[4]}"
    assert labels[5] == i_kwota, f"',' → I-KWOTA, got {labels[5]}"
    assert labels[6] == i_kwota, f"'28' → I-KWOTA, got {labels[6]}"
    assert all(lab == IGNORE for lab in labels[7:]), "SEP/PAD → IGNORE"


@pytest.mark.integration
def test_uc74_integration_smoke_train(tmp_path: Path) -> None:
    """UC-74: integration main([smoke_config]) on CPU — 5 docs, 1 step;

    eval_results.json exists with metrics.
    """
    fixture_src = Path("tests/training/fixtures/smoke_docs.jsonl")
    fixture_dst = tmp_path / "smoke_docs.jsonl"
    fixture_dst.write_text(fixture_src.read_text(encoding="utf-8"), encoding="utf-8")

    out_dir = tmp_path / "out"
    config_data = {
        "run": "pii-4-smoke",
        "base_checkpoint": "hf-internal-testing/tiny-random-BertForTokenClassification",
        "base_revision": "main",
        "train_file": str(fixture_dst),
        "eval_file": str(fixture_dst),
        "seed": 42,
        "max_steps": 1,
        "per_device_batch_size": 2,
        "learning_rate": 5e-5,
        "max_length": 128,
        "output_dir": str(out_dir),
        "threshold": None,
    }
    cfg_file = tmp_path / "pii-4-smoke.yaml"
    cfg_file.write_text(yaml.dump(config_data), encoding="utf-8")

    ret = main([str(cfg_file)])
    assert ret == 0

    eval_results_file = out_dir / "eval_results.json"
    assert eval_results_file.exists()
    results = json.loads(eval_results_file.read_text(encoding="utf-8"))
    assert any(
        k in results
        for k in ["eval_precision", "precision", "eval_f1", "f1", "eval_recall", "recall"]
    )
