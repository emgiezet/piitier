# MVP plan: a Polish PII anonymisation model for fintech, insurtech and medtech

**Recommendation: for the MVP, build a hybrid of deterministic validators (PESEL, NIP, REGON, IBAN, ID card, policy number, etc.) + a small encoder token-classification model (~300M parameters, fine-tuned on Polish domain data) + a deterministic placeholder renderer with consistent numbering. Do not train a generative LLM to rewrite text.** A generative Bielik/Qwen is useful in this project for generating synthetic data, an optional second pass on hard cases, and red-teaming. It should not be the masking engine. The market has moved over the past 12 months (OpenAI released an open Privacy Filter; bards.ai released a Polish PII model), so competitive advantage has to come from the Polish benchmark, domain taxonomy, and guaranteed text fidelity.

## TL;DR

- Approach: hybrid of regex/checksums + encoder NER (e.g. mmBERT/XLM-R/HerBERT, starting from an existing PII checkpoint) + deterministic placeholder substitution. This achieves the highest attainable recall, does not hallucinate, does not modify text beyond entity spans, and runs on CPU. Treat a generative LLM as a tool for data generation and evaluation.
- Data and hardware: for the MVP, an order of 5–20 thousand synthetic, automatically annotated Polish documents and a manually verified gold set of 500–1000 documents is sufficient. Encoder training takes hours on a single RTX 3090 Ti, so a third card is not needed right now. Run large training jobs in the cloud (RTX 4090 from $0.34/h, A100 80 GB approx. $1.39–1.59/h on RunPod) or through PLGrid with an academic partner.
- Funding and competitive edge: the strongest argument for grant-makers and investors will be the first open **Polish PII benchmark for regulated sectors**, combined with a model that measurably beats OpenAI Privacy Filter, Presidio and bards.ai on Polish industry documents (leak rate, recall, fidelity). Plan: 12 weeks part-time to publication on Hugging Face (model + dataset + Space), then a grant application and open-core commercialisation (on-prem, support, domain packages).

## Key findings

1. **A generative LLM is the wrong tool for masking.** It must rewrite the entire text token by token, so it can drop, alter or add fragments, and its outputs differ between runs. Protecto notes in its comparison that "LLM-based redactors may hallucinate, redact too much or too little, and do not provide consistency across runs".\[1\] Even OpenAI built Privacy Filter as a **bidirectional token classifier** (derived from gpt-oss, MoE: 1.5B parameters total, 50M active, Apache 2.0 licence), not a generative model. On PII-Masking-300k it achieves F1 96% (precision 94.04%, recall 98.04%).\[2\]\[3\]\[4\]
2. **The competitive field in Polish is already partially occupied.** bards.ai published `bardsai/eu-pii-anonimization`: a Polish token classifier on XLM-RoBERTa-base, 35 classes, self-reported "Global F1 95%" without a described test set.\[5\] The `eu-pii-anonimization-multilang-v2` variant (mmBERT-base, 307M parameters, 8k context, Apache 2.0) has strict span F1 0.973 on 455 real spans (precision 0.966, recall 0.980).\[6\] **Neither work reports Polish-language results separately.** The OpenAI Privacy Filter model card does not report Polish at all, and GLiNER2-PII (fastino) covers only 7 languages, none of which is Polish.\[2\]\[7\]
3. Market gap: missing are (a) a public Polish PII benchmark with domain-specific documents, (b) domain entities for insurtech/medtech/fintech (policy number, claim number, loan agreement number, ICD-10, land register number, vehicle registration number, VIN), (c) consistent entity numbering that accounts for Polish inflection ("Kowalski"/"Kowalskiego" → the same `[OSOBA_1]`), (d) a hard guarantee that text outside entity spans is byte-for-byte identical.
4. Legal: placeholders with a de-anonymisation map constitute **pseudonymisation, not anonymisation**. For the controller who holds the map, the data remain personal (EDPB, Guidelines 01/2025).\[8\] However, the CJEU in case C-413/23 P (EDPS v SRB, 4 September 2025) adopted a relative approach: pseudonymised data are not personal "in all cases and for every person".\[9\]\[10\] For a recipient without realistic means of re-identification (e.g. an external LLM provider) they may not constitute personal data.\[11\] This is a strong sales argument, but the condition is effective removal of quasi-identifiers too.
5. **Your hardware is sufficient for the MVP.** An encoder of ~300M parameters trains on an RTX 3090 Ti in hours. QLoRA for Bielik 4.5B fits in 24 GB. Buying a new card in 2026 is not cost-effective: the RTX 5090 cost between PLN 24,999 and over PLN 33,000 in Poland in September 2026 against a launch price of PLN 10,299.\[12\]

## 1. Architecture: comparison of approaches

### Comparison table

| Criterion | A. Generative LLM (text-to-text, e.g. Bielik 1.5B/4.5B/11B, Qwen, Gemma, PLLuM) | B. Token classification / NER (HerBERT, XLM-R, mmBERT, GLiNER, Privacy Filter) | C. Hybrid: validators + NER + deterministic renderer (**recommended**) |
|---|---|---|---|
| Recall on structural identifiers (PESEL, IBAN) | medium–high; confuses digits, does not verify checksums | high, but misses unusual formats | **very high** — regex + checksum gives practically 100% on valid numbers |
| Recall on names, addresses, context | high (understands context) | high after domain fine-tuning | high (NER) + optional LLM second pass |
| Hallucination / text-modification risk | **high** — rewrites the entire text | none — returns only offsets | **none** — text modified only within span ranges |
| Consistent numbering `[IMIĘ_1]` (first-name placeholder) | must be trained in, unreliable on long documents | requires post-processing | deterministic module (lemmatisation + matching) |
| Speed / inference cost | slow (generation ~input length), requires GPU | fast, runs on CPU (INT8 ONNX) | fast, CPU; LLM only for uncertain fragments |
| Explainability / auditability | poor | good (span + label + score) | **best** (every decision has a source: rule / model / threshold) |
| Data needed for MVP | tens of thousands of input–output pairs | thousands to tens of thousands of annotated documents | same as B; rules need no data |
| Attractiveness to investors | "sexy", but hard to defend reliability | solid, "boring" | **best story:** "guaranteed fidelity + measurable leak rate + runs on-prem on CPU" |

### Justification of the choice

- Recall is the primary metric. In anonymisation, a single missed PESEL is an incident. Checksum validators provide deterministic certainty for identifiers; the ML model handles what regex cannot: inflected names, free-form addresses, health descriptions.
- Text fidelity. In architecture C the output is produced from the original by substituting ranges `[start, end)`. Text outside entity spans cannot change by definition, and this can be proven by an automated test. An LLM cannot guarantee this.
- Cost. A ~300M model in INT8 ONNX occupies ~0.3 GB (bards.ai reports this for v2: 1.2 GB FP32 → 0.3 GB INT8, with F1 dropping from 0.973 to 0.968).\[6\]\[13\] It runs on CPU in a bank or hospital without a GPU, which in regulated sectors is a prerequisite for adoption.
- For investors and grant-makers, "LLM for anonymisation" sounds attractive. In the narrative, present the AI component honestly: (1) a custom NER model trained on synthetic data generated locally by Bielik, (2) an optional "LLM verifier" (Bielik 1.5B/4.5B checks low-confidence fragments), (3) a roadmap where funding goes toward a larger contextual model, quasi-identifiers, and robustness against LLM inference attacks. The representational power of a generative LLM is not needed here; what is needed is a measurable advantage.

### Target MVP pipeline

1. Input normalisation (Unicode NFC, preserving original offsets).
2. Rules layer: PESEL (11 digits, checksum, valid date), NIP (10 digits, weights), REGON (9/14), IBAN PL (mod 97), ID card number (3 letters + 6 digits, checksum), passport, payment cards (Luhn), phone numbers, email addresses, postal codes, vehicle registration numbers, VINs, land register numbers, and configurable customer patterns (policy number, claim number, agreement number). Numbers that fail checksum validation are not discarded; they are flagged as "suspicious". A typo in a PESEL is still a PESEL.
3. NER model (BIO/BIOES, window of 512–8k tokens): persons, addresses, locations, organisations, dates of birth, health data, job titles, amounts, and other contextual categories.
4. Fusion: a rule with a valid checksum wins; on label conflicts a priority order applies. Set the model threshold for recall, e.g. to achieve ≥0.98 on the validation set.
5. Coreference and numbering: lemmatisation (Morfeusz 2 / spaCy pl) and case normalisation so that "Jan Kowalski", "Kowalskiego", "J. Kowalski" → `[OSOBA_1]`. The same IBAN → `[IBAN_1]`.
6. Renderer: `mask` mode (placeholders), `pseudonymize` mode (placeholders + encrypted map, e.g. AES-GCM with TTL) and `synthetic` mode (realistic data from Faker pl_PL with valid checksums and consistent inflection; this last mode is a post-MVP extension).
7. Optional LLM verifier: Bielik 1.5B/4.5B receives the *already masked* text and responds whether any identifying data remain. The model flags a fragment; the decision is taken by code, so the LLM never generates output.

Encoder choice: start with fine-tuning `bardsai/eu-pii-anonimization-multilang-v2` (Apache 2.0, 8k context, Polish examples already in training) or `openai/privacy-filter` (Apache 2.0, 128k context, but only 8 categories).\[2\]\[6\] As a Polish baseline from scratch, use HerBERT-large or Polish RoBERTa. On Polish NER (PolEval 2018/NKJP), HerBERT large achieved a score of 92.1 and F1 exact 89.9, and Polish RoBERTa base 91.4 (PolDeepNer2, CLARIN-PL).\[14\] Check checkpoint licences before publishing.

## 2. How much training data

Reference points from existing work:

| Work / dataset | Scale | Takeaway |
|---|---|---|
| GLiNER2-PII (fastino) | **4,910** synthetic examples with PII annotations, 42 entity types in 7 categories (arXiv 2605.09973) | authors report that a small, well-designed synthetic dataset was sufficient for the highest span F1 on SPY among five compared systems, including OpenAI Privacy Filter |
| gliner2-PII-basque (tknika) | 2,842 NER sentences + 6,000 synthetic PII sentences (14 types with valid checksums) | adaptation to a new language: micro F1 on PII from 0.742 → 0.845 (v1) → 0.905 (v2)\[15\] |
| NVIDIA Nemotron-PII | 100,000 records (50k/50k), 55+ types, CC BY 4.0 | "production" scale for a single language\[16\]\[17\]\[18\] |
| ai4privacy pii-masking-400k | 406,896 entries, 20.6M tokens, 2.36M PII tokens\[19\] | multilingual scale |
| KPWr (PolEval 2019) | 1,629 documents, >24,000 annotations\[20\] | manual Polish NER corpus, small but real |

Recommended volumes (author's estimates based on the above reference points):

| Approach | MVP | Production |
|---|---|---|
| NER/hybrid (recommended) | 5–20k synthetic documents (~2–10M tokens) + 500–1000 gold-set documents (min. ~100 occurrences of each entity type in test) | 50–150k documents, including at least several thousand real, pseudonymised documents from partners (in accordance with GDPR), min. ~1,000 occurrences per type in training |
| Generative LLM (for comparison) | 20–50k input → masked-output pairs | 100–300k pairs + preference data (DPO) penalising text modification |
| Rules | 0 training examples, but ~50–200 test cases per validator | same + property-based tests (generator of valid and invalid numbers) |

## 3. Data sources for Polish

Ready-made datasets (check licences!):
- **ai4privacy `pii-masking-openpii-1.5m`** (CC BY 4.0, 1.64M rows, 30 languages including Polish) and `openpii-1m` (1,428,143 examples, 23 European languages, 19 types).\[21\]\[22\] The exact number of Polish samples is not published; check it with a `language='pl'` filter in Data Studio. The ai4privacy domain datasets (e.g. `pii-masking-financial-pfi-400k`, `pii-masking-health-phi-400k`) require terms acceptance, and `phi-masking-100k` in its full version is commercial ("All Rights Reserved").\[23\]\[24\]
- **NVIDIA Nemotron-PII** (CC BY 4.0, English), suitable for translating or adapting the document structure and taxonomy.\[25\]
- **KPWr-NER** (`clarin-pl/kpwr-ner`, CC BY 3.0, 82 classes)\[26\] and **NKJP / PolEval 2018**: real Polish proper nouns with inflection; map them to your own taxonomy (person, location, organisation).
- Court rulings (SAOS / court ruling portals): court texts are already anonymised, so they do not provide "gold" personal data. They are useful as realistic legal-language templates into which you inject synthetic data in place of anonymisation markers.
- Medical: public Polish clinical datasets with personal data practically do not exist. Generate synthetic documentation (discharge summaries, referrals, epicrises) with ICD-10 codes and drug names from public registers.

Synthetic generation (primary source):
1. Templates + Faker pl_PL: names with inflection (Morfeusz for generating case forms), addresses from TERYT, PESEL consistent with date of birth and gender, NIP/REGON/IBAN with valid checksums. Labels are perfect by construction, since you know the offsets of the injected values.
2. Local LLM (Bielik 11B/4.5B, PLLuM, Qwen) as document writer: generates the content of an insurance policy, claim notification, loan agreement, account statement, customer correspondence, hospital discharge summary, call-centre chat, with placeholders in place of PII. Code then injects Faker values and knows the exact offsets. Do not let the LLM label entities independently; that is a source of noise.
3. "Dirt" augmentation: typos, missing Polish diacritics, OCR errors (0/O, 1/l), numbers split by spaces, all-caps, tables, emails with signatures.
4. Hard negatives: surnames that are common nouns (Kowal, Wróbel, Zima), street names derived from surnames, technical numbers that look like a PESEL but fail the checksum, public figures. These prevent precision from dropping.

Licences and GDPR:
- 100% synthetic data are not personal data, so publishing the dataset on HF is safe. Still check that the LLM has not "recited" real people; filter out names of known individuals or draw names exclusively from Faker.
- Employer or customer data: **do not use without a contract and legal basis**. The safe path is an evaluation set processed only on-prem at the partner site (the model travels to the data, not the other way around), under a data-processing agreement or NDA, without publication.
- The output dataset licence must be compatible with the sources (CC BY 4.0 requires attribution; CC BY 3.0 KPWr: likewise). The base model licence (Apache 2.0 vs Bielik/PLLuM licences) determines the derived model licence.

## 4. Entity taxonomy and legal framework

### Proposed MVP taxonomy (~30 types, 6 groups)

| Group | Entities (placeholder) | Method |
|---|---|---|
| Person identification | `[OSOBA_n]`, `[IMIĘ_n]`, `[NAZWISKO_n]`, `[DATA_URODZENIA]`, `[WIEK]`, `[PŁEĆ]` | NER |
| State identifiers | `[PESEL]`, `[NR_DOWODU]`, `[NR_PASZPORTU]`, `[NR_PRAWA_JAZDY]`, `[NIP]` (natural person), `[REGON]` | regex + checksum |
| Contact and location | `[ADRES_n]`, `[KOD_POCZTOWY]`, `[MIEJSCOWOŚĆ]`, `[TELEFON]`, `[EMAIL]`, `[IP]`, `[GEO]` | regex + NER |
| Finance (fintech) | `[IBAN]`, `[NR_RACHUNKU]`, `[NR_KARTY]`, `[CVV]`, `[NR_UMOWY]`, `[KWOTA]` (optional), `[DOCHÓD]` | regex + Luhn/mod97 + NER |
| Insurance (insurtech) | `[NR_POLISY]`, `[NR_SZKODY]`, `[NR_REJESTRACYJNY]`, `[VIN]`, `[NR_KW]` | configurable patterns + NER |
| Health (GDPR Art. 9, medtech) | `[DANE_ZDROWOTNE]`, `[ROZPOZNANIE]`, `[ICD10]`, `[LEK]`, `[NR_DOKUMENTACJI]`, `[PLACÓWKA]`, `[LEKARZ_n]`, `[NPWZ]` | NER + dictionaries + regex |
| Other Art. 9/10 | ethnic origin, political views, religion, trade-union membership, sexual orientation, biometrics, criminal records | NER (hard; see roadmap) |
| Quasi-identifiers | job title, employer, rare events, event dates | NER + policy (reported but not always masked in MVP) |

The bards.ai taxonomy (35 classes, including HEALTH_DATA, CRIMINAL_OFFENCE_DATA, ORGANIZATION_IDENTIFIER for company NIP/REGON) is a good reference point.\[13\]\[27\] Mapping it to your labels will make comparison easier.\[6\]

### Legal framework: what you need to know (not legal advice)

- GDPR, anonymisation vs pseudonymisation: anonymised data (recital 26) fall outside GDPR; pseudonymised data (Art. 4(5)) do not. The EDPB in Guidelines 01/2025 stresses that pseudonymisation alone usually does not suffice for compliance, but supports minimisation, privacy by design (Art. 25) and security (Art. 32). It also introduces the concept of a "pseudonymisation domain".\[28\]\[29\]\[30\] The CJEU in ruling C-413/23 P (4 September 2025) confirmed the relative approach: for a recipient who realistically cannot identify a person, the data may not be personal. The controller must still inform data subjects about recipients.\[11\]\[31\] Product implication: `mask` mode without a map, supported by quasi-identifier removal, approaches anonymisation from the perspective of an external LLM provider. `pseudonymize` mode with a secured map is pseudonymisation. Neither claim should be made without legal review of the specific deployment.
- GDPR Art. 9: health data are a special category, so in medtech and in health/life insurance, recall on this class is critical.
- EU AI Act (Regulation 2024/1689): an anonymisation tool itself is unlikely to be a high-risk AI system. It does, however, help customers meet data governance (Art. 10) and privacy-in-the-AI-lifecycle requirements. The timeline for obligations on high-risk systems was subject to proposed delays (the "digital omnibus" package) during 2025–2026; verify the current state before writing a grant application.
- DORA (applicable from 17 January 2025): in finance and insurance, ICT risk management and third-party provider governance. Sending customer data to an external LLM is an ICT provider risk; a local, open on-prem filter mitigates it. This is a sales argument for CISOs.
- Sectoral secrecy: banking secrecy (Art. 104 of the Banking Law), insurance secrecy (Art. 35 of the Insurance and Reinsurance Activity Act), medical secrecy (Art. 40 of the Act on the Professions of Physician and Dentist), and patient rights to confidentiality and documentation (Act on Patient Rights and the Patient Rights Ombudsman). These cover information that is not "classic PII" (e.g. the fact of holding a loan or a medical history), so the taxonomy needs to go beyond names and PESELs.

## 5. Training on your hardware

What is feasible on RTX 3090 Ti 24 GB + RTX 3080 10 GB (estimates):

| Task | Card | Method | Estimated time |
|---|---|---|---|
| Encoder ~300M (mmBERT/XLM-R base), 20k documents × 512 tokens, 3–5 epochs | 3090 Ti | full fine-tuning, bf16 | ~1–4 h |
| HerBERT-large / XLM-R large (~560M) | 3090 Ti | full fine-tuning, bf16, gradient checkpointing | ~3–8 h |
| Bielik 1.5B (generator / verifier) | 3090 Ti | LoRA bf16 or full FT with 8-bit Adam | several hours on 10–30k examples |
| Bielik 4.5B | 3090 Ti | QLoRA 4-bit (Unsloth) | ~10–20 h on 30k examples ~1k tokens |
| Bielik 11B | 3090 Ti | QLoRA 4-bit, short context, small batch | feasible but marginal; better in the cloud |
| Bielik 11B/4.5B inference for data generation | 3090 Ti (+3080) | vLLM / llama.cpp, quantisation | tens of thousands of documents per day (depending on length) |
| Evaluation, baselines, Presidio, demo | 3080 10 GB | inference | in parallel with training on 3090 Ti |

Frameworks:
- Encoder: **HF Transformers `Trainer` + `datasets` + `seqeval`** (or the GLiNER / GLiNER2 library if going zero-shot). Export to ONNX with INT8 quantisation (Optimum).
- LLM: **Unsloth** on a single card; the free version is fastest on one GPU. Multi-GPU in Unsloth works via Accelerate/DDP, but "enhanced multi-GPU" is the Pro version.\[32\]\[33\]\[34\] **Axolotl** (FSDP/DeepSpeed ZeRO, free) or **HF TRL + PEFT** when multiple cards are needed.\[35\]
- Unequal cards: DDP and FSDP synchronise to the slowest and smallest card, so the 3080 10 GB will constrain batch size and model size. Do not combine them in one training run. Use the 3090 Ti for training and the 3080 for data generation, evaluation and demo. Alternatively, partition the model across cards by layer (`device_map="balanced"`) for inference of large models only.\[33\]

Should you buy a third card? Not now.
- The RTX 5090 (32 GB) cost between PLN 24,999 and PLN 33,091 in Poland on 14 September 2026 (median PLN 27,872) against a launch price of PLN 10,299.\[12\] For that amount you can buy thousands of hours of RTX 4090 in the cloud.
- If you must buy, get a used RTX 3090 24 GB: the same architecture as the 3090 Ti, giving a symmetric 2×24 GB pair for DDP or FSDP. Verify second-hand prices yourself, as I have not checked them. Also bear in mind the PSU (≥1200–1600 W for two 3090s) and airflow.
- Cloud (RunPod, 2026): RTX 4090: $0.34/h (Community) / $0.69–0.74/h (Secure); RTX 5090: approx. $0.99/h; A100 80 GB: $1.19–1.59/h; H100 PCIe: $1.99–2.89/h.\[36\]\[37\]\[38\] A market example: a 20-hour QLoRA run on an A100 costs ~$28.\[39\] Vast.ai is sometimes cheaper (marketplace); Lambda is more expensive (H100 SXM ~$3.99/h).\[40\] **Cloud budget for the entire MVP: ~$50–300.**
- PLGrid (Cyfronet): Athena (nodes with 8× A100 40 GB) and Helios (440× GH200 96 GB).\[41\]\[42\] Grants can only be applied for by people with an academic affiliation (university or institute employee, doctoral student), and a pilot grant provides 1,000 compute hours.\[43\] **Requires an academic partner**, which is also a good move for R&D grant applications.

## 6. Evaluation

Metrics (report all, per entity type and per domain):
- Recall and precision at entity level (strict and partial match; seqeval). Risk-weighted recall: PESEL, IBAN and a diagnosis carry more weight than a locality name.
- Leak rate: the share of documents in which any direct identifier remains after masking, and the share of "PII values" (string-matching originals in the output). This is the primary business metric. MVP target: <1% of documents with a direct-identifier leak on the gold set.
- Text fidelity outside entity spans: after removing spans, the character difference must be exactly 0 (automated test). For comparison with LLMs: chrF/normalised edit distance.
- Numbering consistency: the share of mention pairs about the same person that received the same placeholder (and different persons get different placeholders).
- Utility: the same downstream task (claim summarisation, complaint classification, policy data extraction) performed by an external LLM on the original and on the masked version, with quality comparison.
- Performance: documents/s on CPU and GPU, p95 latency, RAM.

Gold test set: 500–1000 documents across 6–8 types (insurance policy, claim notification, loan agreement, account statement, customer email, call-centre transcript, hospital discharge summary, referral). Approximately 70% realistic synthetic documents written manually or by LLM and manually corrected, approximately 30% "hard" cases. Two annotators, annotation guidelines, inter-annotator agreement Cohen's kappa/F1. Publish it as **PL-PII-Bench** (a separate dataset on HF); it is your most important marketing and grant asset.

Red-teaming and re-identification:
- Format attacks: PESEL with spaces, written in words, in a table, in a URL, in base64; diminutive names and names in the vocative case; addresses without "ul." (street prefix).
- LLM inference attack: give a powerful LLM the masked text and ask it to infer identity, location or age. Staab, Vero, Balunović and Vechev (ETH Zurich) in "Language Models are Advanced Anonymizers" (ICLR 2025), testing 13 LLMs as well as Presidio and Azure Language Services, found that "current industry-standard text anonymizers are largely insufficient at protecting users from such attacks, as they are unable to pick up on revealing yet complex and context-dependent cues". Measure this as a separate metric "residual inference risk" (a good space for the grant roadmap).
- Linking attack: several documents for the same customer → can an identity be reconstructed from quasi-identifiers?

Baselines for the comparison table:
1. Microsoft Presidio (with Polish spaCy): "out of the box" variant and with Polish recognisers.
2. `anon-legal-pl` (Presidio + spaCy `pl_core_news_lg` + optional Bielik via Ollama, PESEL/NIP/REGON validation, Apache 2.0).\[44\]\[45\]
3. `bardsai/eu-pii-anonimization` (PL) and `-multilang-v2`.
4. `openai/privacy-filter` (Apache 2.0, no results for Polish).
5. GLiNER-PII (knowledgator, NVIDIA): zero-shot with Polish labels.
6. Zero-shot LLM: Bielik 11B v3 with a masking prompt, and GPT/Claude (on synthetic data only!).
7. Optionally commercial: Limina (formerly Private AI), trial.

Context from the literature: in the LLM-Anonymizer benchmark (Wiest et al., team of J.N. Kather, NEJM AI 2(4), March 2025, DOI 10.1056/AIdbp2400537; 250 real clinical letters, German) "CliniDeID and Presidio anonymized PII in the clinical letters with lower sensitivity (0.84 and 0.82, respectively) on a character-wise basis", a local Llama-2 7B had sensitivity ~0.84, and the best local Llama-3 70B: 99.24% (0.76% PII missed). Generic tools therefore leave ~16–18% of identifiers in medical documents, which justifies a domain-specific model.

## 7. Competition and market

| Solution | Type | Polish? | Notes |
|---|---|---|---|
| Microsoft Presidio | open source (MIT), framework | via extensions | de facto standard; quality depends on added models |
| OpenAI Privacy Filter | open-weight, Apache 2.0 | no reported results | 8 categories, 128k context, F1 96% (EN, PII-Masking-300k); OpenAI notes this is not a certified anonymisation tool\[2\]\[3\]\[46\] |
| GLiNER2-PII (fastino), GLiNER-PII (knowledgator, NVIDIA) | open source | no (7 languages) / zero-shot | knowledgator gliner-pii-base-v1.0: F1 80.99% (precision 79.28%, recall 82.78%) on synthetic-multi-pii-ner-v1 per HF card, but only 0.368 mean span F1 on SPY benchmark (arXiv 2605.09973) |
| bards.ai eu-pii-anonimization (PL, multilang, v2) | open source, Apache 2.0 (multilang) | **yes** | closest competitor; no Polish benchmark and no domain entities |
| pii.tools | open source, Apache 2.0, browser (WASM) | yes | 35 types, based on bards.ai models\[47\] |
| anon-legal-pl, matematic-anonimizacja-pl, priv-masker (NASK spaCy) | open source | yes | rules + spaCy; law and administration |
| Bluur (BTC), Redactable | commercial | yes | document anonymisation, mainly law/administration\[48\] |
| Limina (formerly Private AI) | commercial, on-prem container | 52 languages | 50+ entity types, redaction/pseudonymisation/synthesis; Series A in 2022: $8M (CAD 10.7M, BetaKit); rename to Limina announced 5 March 2026 with no impact on products or customers (getlimina.ai) |
| Protecto | commercial, privacy vault | 50+ languages | 200+ PII/PHI/PCI types\[49\] |
| Skyflow | commercial, vault + tokenisation | n/a | strong in fintech (PCI DSS)\[50\] |
| Nightfall | commercial, DLP | n/a | protection of AI use by employees\[51\] |

Gaps worth targeting:
1. Polish documents in regulated sectors: insurtech/medtech/fintech entities absent from generic taxonomies.
2. A reliable public Polish benchmark: nobody has one, and customers and grant-makers need it.
3. Consistent pseudonymisation with inflection and a reversible map (round-trip: mask → external LLM → unmask in the correct grammatical form).
4. On-prem gateway for LLM (OpenAI-compatible proxy) with audit: "prove that PII never left the company".\[52\]

## 8. Funding

| Source | For whom | Amount / deadline | Fit |
|---|---|---|---|
| **NLnet / NGI Zero Commons Fund** | individuals and organisations | €5–50k; **last call closed 1 June 2026**; NLnet runs other programmes (next deadline 3 November 2026) | ideal for open source; check current NLnet programmes\[53\]\[54\] |
| **FENG SMART Path (PARP, SME)** | SMEs based in Poland | B+R call 29 October–29 December 2026, budget PLN 500M; in call I/2026 min. PLN 3M R&D costs, up to 80% co-financing | too large for the MVP; realistic for a company after MVP, with an academic partner\[55\]\[56\]\[57\] |
| **NCBR** (R&D programmes, thematic AI calls) | companies, academia–industry consortia | variable | monitor; a strong argument is a consortium with a university (PLGrid!) |
| **EIC Accelerator / Horizon Europe (Cluster 4, AI & data)** | startups / consortia | large grants + equity | after market validation; "trustworthy AI" and data sovereignty are matching themes |
| Prototype Fund | n/a | n/a | German programme, for people in Germany; largely inaccessible |
| Accelerators and VC in CEE (AI/regtech) | company | pre-seed/seed | required: MVP, benchmark, 2–3 LOIs from industry companies |
| **SpeakLeash/Bielik, PLLuM ecosystem** | community | informally | credibility, data, co-authors, compute access (collaboration with ACK Cyfronet) |

What the MVP and demo must include to be convincing:
1. Benchmark table on PL-PII-Bench: your model vs Presidio, OpenAI Privacy Filter, bards.ai, Bielik zero-shot: recall, leak rate, fidelity, CPU latency.
2. Live demo (HF Space): paste a claim notification or discharge summary → see highlighted entities → masked version → external LLM response → unmasking. With a counter "0 characters changed outside entity spans".
3. Gateway in 5 minutes: `docker run`, OpenAI-API-compatible endpoint that masks on the fly.
4. 2–3 letters of intent from insurtech, fintech or medtech companies (your network and the Bielik community) and a pilot description.
5. Roadmap "what the money will go towards": larger contextual model, quasi-identifiers, robustness against LLM inference, OCR/PDF, additional CEE languages, external certification/audit.

## 9. Action plan (12 weeks, 1 person part-time ~10–15 h/week)

| Week | Milestone | Deliverable |
|---|---|---|
| 1 | Taxonomy + annotation guidelines + repo | `TAXONOMY.md`, JSON span schema, licence decision (Apache 2.0) |
| 2 | Rules layer + property-based tests | PESEL/NIP/REGON/IBAN/ID card/Luhn/policy pattern validators; >200 tests |
| 3–4 | Synthetic data generator | templates for 8 document types, Faker pl_PL + Morfeusz, Bielik locally as document writer; 10–20k documents |
| 4–5 | Gold set v0.1 | 300 manually verified documents (target 500–1000), second annotator on a sample |
| 5 | Baselines | Presidio, anon-legal-pl, bards.ai, Privacy Filter, GLiNER, Bielik zero-shot results |
| 6–7 | NER model training v1 | fine-tuning 2–3 candidates (mmBERT/bards v2, XLM-R, HerBERT), selection, threshold calibration for recall |
| 8 | Fusion + coreference + renderer | `mask` and `pseudonymize` modes (encrypted map), fidelity test = 0 changes |
| 9 | Red-teaming + data iteration | hard negatives, OCR augmentation, model v2; leak rate report |
| 10 | Export and packaging | ONNX INT8, `pip` library, Docker gateway (OpenAI-compatible) |
| 11 | Publication on Hugging Face | model card (use cases, limitations, per-entity metrics, "this is not an anonymisation certificate"), dataset card (synthetic nature, source licences), PL-PII-Bench, Space (Gradio) |
| 12 | Funding materials | one-pager, 10-slide deck, technical blog post, NLnet or other programme submission, LOI conversations |

Small team (2–3 people): the same scope in ~6–8 weeks, with an additional annotator/domain expert (insurance/medicine) and a larger gold set.

HF publication checklist:
- Model: Apache 2.0 (if the base model permits), card with per-entity-type and per-domain metrics table, known limitations (quasi-identifiers, Art. 9 data in colloquial language), usage examples, ONNX versions.
- Dataset: synthetic training corpus (CC BY 4.0) + separate PL-PII-Bench (with a locked or versioned test split to avoid contamination).
- Space: demo with masking modes, span visualisation, "send to LLM and unmask" button.

Open-core and monetisation:
- Open source (Apache 2.0): base model, rules, library, benchmark.
- Enterprise: domain packages (insurtech/medtech/banking) fine-tuned on customer data on-prem; gateway with audit, RBAC, map management (vault, TTL, HSM); PDF/OCR support; SLA and support; on-prem/air-gapped deployments.
- Services: fine-tuning on customer data at the customer's site, leak-rate audit before AI deployment, training (your Bielik trainer role is an asset).
- Certification: external methodology audit (e.g. with a GDPR law firm or academic centre) as a premium product. Do not promise an "anonymisation certificate"; no such formal GDPR certificate exists.

## Caveats

- Estimates: data volumes, training times and cloud budgets are engineering estimates based on comparable work, not measured results. Verify them with a first run.
- **Competitor results are largely self-reported** (bards.ai "F1 95%", OpenAI 96% on an English benchmark). Nobody publishes reliable numbers for Polish, so a proprietary benchmark is necessary, not optional. The bards.ai v2 results on Nemotron and OpenPII are not held-out, since those datasets were in training.\[6\]
- **GPU prices** in Poland were extremely volatile in 2026. Second-hand RTX 3090 prices have not been verified. Cloud prices differ by source and date.
- Funding: the last NGI Zero Commons Fund call is closed.\[53\] The SMART Path requires a company entity and a large R&D budget. Details of NCBR, EIC and CEE investor programmes require up-to-date verification.
- Legal: the GDPR, AI Act, DORA and sectoral secrecy descriptions are indicative and require legal consultation, especially regarding the status of the AI Act timeline extension and whether a specific masking mode meets the anonymisation threshold in a given context.
- Conflict of interest: ensure that your employment contract does not assign project rights to your employer, and that you are not using company data or resources without consent.

## Sources

1. [Comparing Best NER Models For PII Identification](https://www.protecto.ai/blog/best-ner-models-for-pii-identification/)
2. <https://arxiv.org/html/2608.18274v1>
3. [Introducing OpenAI Privacy Filter](https://openai.com/index/introducing-openai-privacy-filter/)
4. [OpenAI Releases Privacy Filter: A 1.5B-Parameter Open-Source PII Redaction Model with 50M Active Parameters - MarkTechPost](https://www.marktechpost.com/2026/04/28/openai-releases-privacy-filter-a-1-5b-parameter-open-source-pii-redaction-model-with-50m-active-parameters/)
5. [bardsai/eu-pii-anonimization · Hugging Face](https://huggingface.co/bardsai/eu-pii-anonimization)
6. [bardsai/eu-pii-anonimization-multilang-v2 · Hugging Face](https://huggingface.co/bardsai/eu-pii-anonimization-multilang-v2)
7. [fastino/gliner2-privacy-filter-PII-multi · Hugging Face](https://huggingface.co/fastino/gliner2-privacy-filter-PII-multi)
8. [The new EDPB guidelines on pseudonymization - LEXIA](https://www.lexia.it/en/2025/02/26/edpb-guidelines-pseudonymization/)
9. [CJEU clarifies concept of personal data for a transfer of pseudonymised data to third parties](https://www.aoshearman.com/en/insights/ao-shearman-on-data/cjeu-clarifies-concept-of-personal-data-for-a-transfer-of-pseudonymised-data-to-third-parties)
10. [Personal Data or Not? CJEU Weighs In on Pseudonymisation in EDPS v. SRB](https://www.goodwinlaw.com/en/insights/publications/2025/09/alerts-technology-dpc-personal-data-or-not)
11. [EU Court of Justice Clarifies Definition of "Personal Data" in the Context of Pseudonymization](https://www.hunton.com/privacy-and-cybersecurity-law-blog/eu-court-of-justice-clarifies-definition-of-personal-data-in-the-context-of-pseudonymization)
12. [Dlaczego RTX 5090 kosztuje w Polsce 25 000 zł](https://devstockacademy.pl/blog/branza-it-i-nowe-technologie/rtx-5090-cena-polska-25-tysiecy-2026/)
13. [PII Anonymizer](https://eu-pii.bards.ai/)
14. [GitHub - CLARIN-PL/PolDeepNer2: An improved tool for named entity recognition for Polish based on deep learning. · GitHub](https://github.com/CLARIN-PL/PolDeepNer2)
15. [tknika/gliner2-PII-basque · Hugging Face](https://huggingface.co/tknika/gliner2-PII-basque)
16. [--- library\_name: gliner license: other license\_name: nvidia-open-model-license](https://huggingface.co/nvidia/gliner-PII/raw/main/README.md)
17. [GitHub - NVIDIA-NeMo/Nemotron: Developer Asset Hub for NVIDIA Nemotron](https://github.com/NVIDIA-NeMo/Nemotron)
18. [🛡️ Nemotron PII: Synthesized Data for Privacy-Preserving AI](https://huggingface.co/blog/nvidia/nemotron-pii)
19. [ai4privacy/pii-masking-400k · Datasets at Hugging Face](https://huggingface.co/datasets/ai4privacy/pii-masking-400k)
20. [(PDF) PolEval 2019 - the next chapter in evaluating Natural Language Processing tools for Polish](https://www.researchgate.net/publication/334480247_PolEval_2019_-_the_next_chapter_in_evaluating_Natural_Language_Processing_tools_for_Polish)
21. [ai4privacy/pii-masking-openpii-1m · Datasets at Hugging Face](https://huggingface.co/datasets/ai4privacy/pii-masking-openpii-1m)
22. [ai4privacy/pii-masking-openpii-1.5m · Datasets at Hugging Face](https://huggingface.co/datasets/ai4privacy/pii-masking-openpii-1.5m)
23. [ai4privacy/pii-masking-digital-pdi-350k · Datasets at Hugging Face](https://huggingface.co/datasets/ai4privacy/pii-masking-digital-pdi-350k)
24. [README.md · ai4privacy/phi-masking-100k at main](https://huggingface.co/datasets/ai4privacy/phi-masking-100k/blob/main/README.md)
25. [nvidia/Nemotron-PII · Datasets at Hugging Face](https://huggingface.co/datasets/nvidia/Nemotron-PII)
26. [clarin-pl/kpwr-ner · Datasets at Hugging Face](https://huggingface.co/datasets/clarin-pl/kpwr-ner)
27. [GitHub - semprerudi/awesome-pii-redaction: A curated list of resources about PII · GitHub](https://github.com/semprerudi/awesome-pii-redaction)
28. [Guidelines 01/2025 on Pseudonymisation](https://www.edpb.europa.eu/system/files/2025-01/edpb_guidelines_202501_pseudonymisation_en.pdf)
29. [EDPB advises on pseudonymisation for GDPR compliance](https://www.hunton.com/insights/publications/edpb-advises-on-pseudonymisation-for-gdpr-compliance)
30. [EDPB's Draft Guidelines 01/2025 on Pseudonymisation](https://allegiance.law/news/edpbs-draft-guidelines-01-2025-on-pseudonymisation/)
31. [CJEU Ruling on Pseudonymisation: Landmark Case C-413/23 P (EDPS v SRB) and Its Impact on GDPR Compliance](https://sgklegal.gr/en/cjeu-clarifies-scope-of-pseudonymisation/)
32. [Axolotl vs Unsloth vs TorchTune: Best LLM Fine-Tuning Frameworks in 2026](https://www.spheron.network/blog/axolotl-vs-unsloth-vs-torchtune/)
33. [Multi-GPU Fine-tuning with Unsloth](https://unsloth.ai/docs/basics/multi-gpu-training-with-unsloth)
34. [Pricing](https://www.unsloth.ai/pricing)
35. [unsloth-vs-axolotl-2026 - DEV Community](https://dev.to/jovan_chan_9500711396d4e6/unsloth-vs-axolotl-2026-18e1)
36. [GPU Cloud Pricing Comparison: Runpod vs Vast.ai (2026)](https://www.spheron.network/blog/gpu-cloud-pricing-comparison-runpod-vs-vastai-2026/)
37. [Top 12 Cloud GPU Providers for AI and ML in 2026](https://www.runpod.io/articles/guides/top-cloud-gpu-providers)
38. [RunPod Pricing](https://www.usagepricing.com/blueprint/runpod)
39. [RunPod vs Glows.ai: 7 Numbers Before You Rent a GPU](https://glows.ai/article/runpod_vs_glows_ai_en)
40. [RunPod vs Lambda vs Vast.ai: GPU Pricing 2026 - Tech Insider](https://tech-insider.org/runpod-vs-lambda-vs-vast-ai-2026/)
41. [Athena - Maciej Pawlik - Confluence](https://docs.cyfronet.pl/display/~plgpawlik/Athena)
42. [Offer - PLGrid](https://www.plgrid.pl/offer)
43. [Granty PLGrid](https://guide.plgrid.pl/pl/grants/plgrid)
44. [anon-legal-pl: anonimizacja dokumentów prawnych offline](https://www.ktzr.pl/legal-tech/anon-legal-pl/)
45. [GitHub - apiotrowski-afk/anon-legal-pl: Local-first PII anonymizer for Polish legal documents, built on Microsoft Presidio + spaCy. PESEL/NIP/REGON checksums, court-signature patterns, optional Bielik (local LLM) + OCR. 100% offline. Apache 2.0.](https://github.com/apiotrowski-afk/anon-legal-pl)
46. [OpenAI's Privacy Filter: Open-Weight PII Redaction Model (Xcelit)](https://www.xcelit.co.in/news/openais-privacy-filter-open-weight-pii-redaction-model)
47. [pii.tools: anonimizacja PII w przeglądarce](https://pii.tools/)
48. [Systemy do anonimizacji dokumentów](https://bluur.ai/pl/bluur-vs-redactable)
49. [Data Privacy Vault For AI & PII Protection](https://www.protecto.ai/product/privacy-vault/)
50. [Best PII Tokenization Software for LLMs (2026)](https://www.enigmavault.io/blog/best-pii-tokenization-software-for-llms/)
51. [Best AI Data Security Software for Enterprises (2026)](https://www.enigmavault.io/blog/best-ai-data-security-software-for-enterprises/)
52. [privacy-kit/README.md at main · bards-ai/privacy-kit · GitHub](https://github.com/bards-ai/privacy-kit/blob/main/README.md)
53. [NLnet; NGI Zero Commons Fund](https://nlnet.nl/commonsfund/)
54. [NLnet; About NGI Zero](https://nlnet.nl/NGI0/)
55. [Ścieżka SMART 2026 dla MŚP](https://openconcept.pl/sciezka-smart-2026-dla-msp-nabor-ogloszony-jesli-chcesz-zdazyc-musisz-zaczac-teraz/)
56. [Ścieżka SMART 2026 dla MŚP: nabór PARP na projekty B+R](https://mdotacje.pl/sciezka-smart-parp-2026/)
57. [Nabór FENG 003/26 w Ścieżce SMART](https://www.innology.pro/czytelnia/czy-to-juz-ostatni-konkurs-na-prace-b-r-w-ramach-sciezki-smart)
