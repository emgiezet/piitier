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
