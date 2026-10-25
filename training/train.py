from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np
import seqeval.scheme
import torch
from seqeval.metrics import f1_score, precision_score, recall_score
from torch.utils.data import Dataset
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    EvalPrediction,
    Trainer,
    TrainingArguments,
)

from piitier.labels import Label
from piitier.ner.inference import bio_tag_names, spans_to_token_labels
from piitier.spans import Span
from training.config import TrainingConfig, load_config


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


class NerDataset(Dataset[dict[str, torch.Tensor]]):
    def __init__(
        self,
        input_ids: list[list[int]],
        attention_mask: list[list[int]],
        labels: list[list[int]],
    ) -> None:
        self.input_ids = torch.tensor(input_ids, dtype=torch.long)
        self.attention_mask = torch.tensor(attention_mask, dtype=torch.long)
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.input_ids)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        return {
            "input_ids": self.input_ids[idx],
            "attention_mask": self.attention_mask[idx],
            "labels": self.labels[idx],
        }


def build_dataset(
    records: list[dict[str, Any]],
    tokenizer: Any,
    max_length: int,
) -> Dataset[dict[str, torch.Tensor]]:
    texts = [str(r["text"]) for r in records]
    encodings = tokenizer(
        texts,
        return_offsets_mapping=True,
        truncation=True,
        max_length=max_length,
        padding="max_length",
    )

    input_ids_list = []
    attention_mask_list = []
    labels_list = []

    for i, record in enumerate(records):
        raw_spans = record.get("spans", [])
        spans = []
        for s in raw_spans:
            lbl_name = str(s["label"])
            lbl = Label[lbl_name]
            spans.append(
                Span(
                    start=int(s["start"]),
                    end=int(s["end"]),
                    label=lbl,
                    source=str(s.get("source", "train")),
                    score=float(s.get("score", 1.0)),
                    status=str(s.get("status", "valid")),
                )
            )

        offset_mapping = encodings["offset_mapping"][i]
        token_labels = spans_to_token_labels(spans, offset_mapping)
        attn_mask = encodings["attention_mask"][i]

        for j, (start, end) in enumerate(offset_mapping):
            if start == 0 and end == 0 or attn_mask[j] == 0 or start >= end:
                token_labels[j] = -100

        input_ids_list.append(encodings["input_ids"][i])
        attention_mask_list.append(attn_mask)
        labels_list.append(token_labels)

    return NerDataset(input_ids_list, attention_mask_list, labels_list)


def compute_metrics_factory(
    label_names: list[str],
) -> Callable[[EvalPrediction], dict[str, float]]:
    def compute_metrics(p: EvalPrediction) -> dict[str, float]:
        predictions, labels = p
        preds = np.argmax(predictions, axis=2)

        true_predictions = [
            [
                label_names[pred_id]
                for (pred_id, label_id) in zip(prediction, label)
                if label_id != -100
            ]
            for prediction, label in zip(preds, labels)
        ]
        true_labels = [
            [
                label_names[label_id]
                for (pred_id, label_id) in zip(prediction, label)
                if label_id != -100
            ]
            for prediction, label in zip(preds, labels)
        ]

        prec = precision_score(
            true_labels, true_predictions, mode="strict", scheme=seqeval.scheme.IOB2
        )
        rec = recall_score(true_labels, true_predictions, mode="strict", scheme=seqeval.scheme.IOB2)
        f1 = f1_score(true_labels, true_predictions, mode="strict", scheme=seqeval.scheme.IOB2)

        return {
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1": round(float(f1), 4),
        }

    return compute_metrics


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) != 1:
        print("Usage: python -m training.train <config.yaml>", file=sys.stderr)
        return 2

    config_path = Path(argv[0])
    try:
        config: TrainingConfig = load_config(config_path)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 1

    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(config.seed)

    label_names = bio_tag_names()
    label2id = {name: i for i, name in enumerate(label_names)}
    id2label = {i: name for i, name in enumerate(label_names)}

    tokenizer = AutoTokenizer.from_pretrained(config.base_checkpoint, revision=config.base_revision)
    model = AutoModelForTokenClassification.from_pretrained(
        config.base_checkpoint,
        revision=config.base_revision,
        num_labels=len(label_names),
        id2label=id2label,
        label2id=label2id,
        ignore_mismatched_sizes=True,
    )

    train_records = read_jsonl(config.train_file)
    eval_records = read_jsonl(config.eval_file)

    train_dataset = build_dataset(train_records, tokenizer, config.max_length)
    eval_dataset = build_dataset(eval_records, tokenizer, config.max_length)

    use_cpu = not torch.cuda.is_available()

    # Single-GPU requirement: launch with CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=1
    # to restrict to the RTX 3090 Ti (CUDA's default fastest-first order makes index 1 the
    # RTX 3080) and keep HF Trainer from pulling both cards into a DataParallel job.
    training_args = TrainingArguments(
        output_dir=str(config.output_dir),
        max_steps=config.max_steps,
        per_device_train_batch_size=config.per_device_batch_size,
        per_device_eval_batch_size=config.per_device_batch_size,
        learning_rate=config.learning_rate,
        seed=config.seed,
        bf16=config.bf16,
        save_strategy="no",
        eval_strategy="no" if config.max_steps == 1 else "steps",
        use_cpu=use_cpu,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        compute_metrics=compute_metrics_factory(label_names),
    )

    trainer.train()
    eval_metrics = trainer.evaluate()

    config.output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(config.output_dir))
    tokenizer.save_pretrained(str(config.output_dir))
    (config.output_dir / "eval_results.json").write_text(
        json.dumps(eval_metrics, indent=2), encoding="utf-8"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
