# Publishing pii-5-v4 → emgiezet/piitier-pl

## Pre-upload checklist

- [ ] Card threshold matches config: `threshold: 0.78` in `training/configs/pii-5-v4.yaml`
      and `--threshold 0.78` in the How to use section of `README.md`.
- [ ] SHA-256 in card matches weights:
      `sha256sum training/out/pii-5-v4/model.safetensors`
      expected: `94d43a6effabd3c3b1500d8f20f9d136aa77b39f2f4fb01fcf51dedd062fc94c`
- [ ] Card copied to output directory (see Copy command below).
- [ ] `training/out/pii-5-v4/` contains `model.safetensors`, `config.json`,
      `tokenizer*`, `model.onnx` (FP32), and `README.md`.
- [ ] YAML front matter parses without error (run `python -c "import yaml; yaml.safe_load(open('training/out/pii-5-v4/README.md').read().split('---')[1])"`).
- [ ] Closing sentence present verbatim: `This is not a certificate of anonymisation.`

## Copy command

```bash
cp training/model_cards/pii-5-v4/README.md training/out/pii-5-v4/README.md
```

## Upload command

Human-run only. The agent never pushes to the Hub.

```bash
hf upload emgiezet/piitier-pl training/out/pii-5-v4 . --repo-type model
```
