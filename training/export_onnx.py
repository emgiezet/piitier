from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

if "eval.metrics" not in sys.modules:
    _metrics_path = Path(__file__).resolve().parent.parent / "eval" / "metrics.py"
    _spec_m = importlib.util.spec_from_file_location("eval.metrics", _metrics_path)
    if _spec_m is not None and _spec_m.loader is not None:
        _metrics_mod = importlib.util.module_from_spec(_spec_m)
        sys.modules["eval.metrics"] = _metrics_mod
        _spec_m.loader.exec_module(_metrics_mod)

from eval.metrics import corpus_entity_metrics
from piitier.labels import Label
from piitier.ner.inference import NerPredictor, bio_tag_names, decode_spans, merge_windows
from piitier.spans import Span
from training.config import ConfigError, load_config
from training.train import read_jsonl


class OnnxNerPredictor:
    """Predictor using ONNX inference session and tokenizer."""

    def __init__(
        self, onnx_path: str | Path, tokenizer_checkpoint: str | Path, threshold: float = 0.0
    ) -> None:
        import onnxruntime as ort
        from transformers import AutoConfig, AutoTokenizer

        self.session = ort.InferenceSession(str(onnx_path))
        self.tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_checkpoint))
        self.threshold = threshold

        cfg = AutoConfig.from_pretrained(str(tokenizer_checkpoint))
        raw_id2label = cfg.id2label
        if raw_id2label:
            self.id2label = {int(k): str(v) for k, v in raw_id2label.items()}
        else:
            tag_names = bio_tag_names()
            self.id2label = {i: name for i, name in enumerate(tag_names)}

    def predict(self, text: str) -> list[Span]:
        if not text:
            return []
        import numpy as np

        encoding = self.tokenizer(
            text,
            return_offsets_mapping=True,
            return_overflowing_tokens=True,
            max_length=512,
            stride=256,
            truncation=True,
            padding="max_length",
            return_tensors="np",
        )

        input_ids = encoding["input_ids"]
        attention_mask = encoding["attention_mask"]
        offset_mappings = encoding["offset_mapping"].tolist()

        all_spans = []
        for w in range(len(input_ids)):
            ort_inputs = {
                "input_ids": input_ids[w : w + 1].astype(np.int64),
                "attention_mask": attention_mask[w : w + 1].astype(np.int64),
            }
            outputs = self.session.run(None, ort_inputs)
            logits = outputs[0]
            logits_exp = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
            probs = (logits_exp / np.sum(logits_exp, axis=-1, keepdims=True))[0].tolist()

            window_spans = decode_spans(
                text=text,
                offset_mapping=offset_mappings[w],
                probs=probs,
                id2label=self.id2label,
                threshold=self.threshold,
            )
            all_spans.extend(window_spans)

        return merge_windows(all_spans)


def export_onnx(checkpoint: str | Path, output_dir: Path) -> Path:
    """Export PyTorch checkpoint to ONNX model using torch.onnx.export."""
    import torch
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    checkpoint_path = Path(checkpoint)
    if (
        not checkpoint_path.exists()
        and not str(checkpoint_path).startswith("hf-internal-testing/")
        and not str(checkpoint_path).startswith("bardsai/")
    ):
        raise ConfigError(f"Checkpoint not found: {checkpoint_path}")

    onnx_dir = output_dir / "onnx"
    onnx_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = onnx_dir / "model.onnx"

    tokenizer = AutoTokenizer.from_pretrained(str(checkpoint_path))
    model = AutoModelForTokenClassification.from_pretrained(str(checkpoint_path))
    model.eval()

    tokenizer.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(onnx_dir))
    model.config.save_pretrained(str(output_dir))
    model.config.save_pretrained(str(onnx_dir))

    text = "Przykładowy tekst testowy."
    inputs = tokenizer(text, return_tensors="pt")

    with torch.no_grad():
        torch.onnx.export(
            model,
            (inputs["input_ids"], inputs["attention_mask"]),
            str(onnx_path),
            input_names=["input_ids", "attention_mask"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "seq"},
                "attention_mask": {0: "batch", 1: "seq"},
                "logits": {0: "batch", 1: "seq"},
            },
            opset_version=18,
        )
    return onnx_path


def quantize_int8(onnx_path: Path, output_path: Path) -> Path:
    """Quantize ONNX model to INT8 using onnxruntime.quantization."""
    from onnxruntime.quantization import QuantType, quantize_dynamic

    output_path.parent.mkdir(parents=True, exist_ok=True)
    quantize_dynamic(
        model_input=str(onnx_path),
        model_output=str(output_path),
        weight_type=QuantType.QInt8,
    )
    return output_path


def score_checkpoint(
    checkpoint_or_dir: str | Path,
    records: list[dict[str, Any]],
    threshold: float | None = None,
) -> tuple[float, float]:
    """Score checkpoint or ONNX model on records. Returns (f1, recall) strict.

    Dispatch rules:
    - path.suffix == ".onnx"  -> OnnxNerPredictor on that exact file.
    - path.is_dir()           -> NerPredictor (PyTorch); never glob for *.onnx.
    """
    thresh = threshold if threshold is not None else 0.0
    path = Path(checkpoint_or_dir)

    if path.suffix == ".onnx":
        tokenizer_ckpt = path.parent.parent if path.parent.name == "onnx" else path.parent
        if not (tokenizer_ckpt / "config.json").exists():
            tokenizer_ckpt = path.parent
        predictor: NerPredictor | OnnxNerPredictor = OnnxNerPredictor(
            path, tokenizer_ckpt, threshold=thresh
        )
    else:
        predictor = NerPredictor(checkpoint=checkpoint_or_dir, threshold=thresh)

    gold_docs: list[list[Span]] = []
    pred_docs: list[list[Span]] = []
    for r in records:
        gold_spans = [
            Span(
                s["start"],
                s["end"],
                Label[s["label"]] if isinstance(s["label"], str) else s["label"],
                s.get("source", "gold"),
                s.get("score"),
                s.get("status", "valid"),
            )
            for s in r.get("spans", r.get("gold", []))
        ]
        pred_spans = predictor.predict(r["text"])
        gold_docs.append(gold_spans)
        pred_docs.append(pred_spans)

    prf = corpus_entity_metrics(gold_docs, pred_docs, match="strict")
    return (float(prf.f1), float(prf.recall))


def exceeds_tolerance(report: dict[str, Any], tol: float) -> bool:
    """Check if recall delta exceeds tolerance."""
    fp32_recall = float(report.get("fp32_recall", 0.0))
    int8_recall = float(report.get("int8_recall", 0.0))
    recall_delta = fp32_recall - int8_recall
    return recall_delta > tol


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) != 1:
        print("Usage: python -m training.export_onnx <config.yaml>", file=sys.stderr)
        return 2

    config_path = Path(argv[0])
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 1

    checkpoint = config.base_checkpoint
    if config.output_dir.exists():
        checkpoints = list(config.output_dir.glob("checkpoint-*"))
        if checkpoints:
            checkpoints.sort(key=lambda p: int(p.name.split("-")[-1]))
            checkpoint = checkpoints[-1]
        elif (config.output_dir / "config.json").exists():
            checkpoint = config.output_dir

    if not checkpoint:
        raise ConfigError("No valid checkpoint found for ONNX export.")

    config.output_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = export_onnx(checkpoint, config.output_dir)
    int8_path = config.output_dir / "model_int8.onnx"
    quantize_int8(onnx_path, int8_path)

    eval_records = read_jsonl(config.eval_file)
    threshold = config.threshold if config.threshold is not None else 0.0

    # Score FP32 on the exported ONNX file (not the PyTorch checkpoint),
    # so the delta isolates only quantisation, not runtime differences.
    fp32_f1, fp32_recall = score_checkpoint(onnx_path, eval_records, threshold)
    int8_f1, int8_recall = score_checkpoint(int8_path, eval_records, threshold)

    f1_delta = float(fp32_f1 - int8_f1)
    recall_delta = float(fp32_recall - int8_recall)

    report = {
        "fp32_f1": fp32_f1,
        "fp32_recall": fp32_recall,
        "int8_f1": int8_f1,
        "int8_recall": int8_recall,
        "f1_delta": f1_delta,
        "recall_delta": recall_delta,
    }

    report_path = config.output_dir / "export_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    tolerance = config.int8_recall_tolerance

    if exceeds_tolerance(report, tolerance):
        print(
            f"Tolerance exceeded: recall_delta ({recall_delta}) > tolerance ({tolerance})",
            file=sys.stderr,
        )
        return 1

    print(f"Export and quantization completed successfully. Report saved to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
