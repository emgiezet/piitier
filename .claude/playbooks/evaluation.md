# Playbook — Metrics, baselines, benchmark runs

Task-scoped. Reached from the Task Router in `CLAUDE.md`. Do not read sibling playbooks.
Conventions for the code live in `.claude/rules/python.md`.

PL-PII-Bench lives in `bench/<version>/{dev,test}/`. `test/` is frozen once a version is
published. Adding or correcting documents creates a new version and never edits the old one.

## Sequence

1. **Metrics live in `eval/metrics.py`**, one function each, and every one is reported
   per entity type and per domain:
   - entity precision and recall, strict and partial match (`seqeval`)
   - risk-weighted recall (weights from `docs/TAXONOMY.md`)
   - leak rate: the share of documents with any direct identifier left, plus the share of
     original PII values that string-match in the output
   - fidelity: characters changed outside spans, which must be 0
   - numbering consistency: same-entity mention pairs that got the same placeholder, and
     different-entity pairs that got different ones
   - throughput (docs/s on CPU and GPU), p95 latency, peak RAM
2. **Baselines are adapters** in `eval/baselines/<name>.py` with one interface:
   `predict(text) -> list[Span]` in TAXONOMY labels. Planned: Presidio (default and with
   Polish recognisers), anon-legal-pl, `bardsai/eu-pii-anonimization` and `-multilang-v2`,
   `openai/privacy-filter`, GLiNER-PII, Bielik zero-shot. Each adapter states its label
   mapping explicitly; an unmapped type is reported as a miss.
3. **External APIs (GPT, Claude, commercial trials) run on synthetic documents only.**
   Never send gold-set or partner documents off the machine.
4. **A benchmark run** is `uv run python -m eval.run --system <name> --bench <version>
   --split <dev|test>`. It writes `eval/reports/<date>-<system>-<bench>-<split>.md` with the
   system name and revision, bench version, threshold, hardware, and every metric from step 1.
5. **`--split test`** is only for final numbers for a model card or publication. Tuning and
   iteration use `dev` (CLAUDE.md invariant 7).

## Test requirements

- Every metric function is checked against a small hand-computed fixture: known spans in,
  exact expected number out, including the zero-prediction and zero-gold edge cases.
- Leak rate counts a document with one residual PESEL as leaked; a document whose leftover
  value is only `suspect` and masked is not leaked.
- Each baseline's label mapping maps every TAXONOMY type or marks it unmapped explicitly.
- One test per acceptance criterion, named with its `UC-<n>` id when working from a spec.

## Verify

Run the verification block from `.claude/rules/python.md`. Then run step 4 for one system
on `--split dev` and check the report file was written with every metric present.

## Done when

Metrics match their hand-computed fixtures, baselines map labels explicitly, the report
records versions and hardware, `test/` is untouched, and the verification block is green.
