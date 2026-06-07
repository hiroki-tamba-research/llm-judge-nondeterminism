# Non-determinism in LLM-as-Judge Graders: An Empirical Reproducibility Note

**Author:** Hiroki Tamba (Tamba Research Academy) · ORCID [0009-0004-7635-0741](https://orcid.org/0009-0004-7635-0741)
**Status:** Preprint / technical note — **v1.0 (report; pre-resolution)**
**DOI:** [10.5281/zenodo.20581781](https://doi.org/10.5281/zenodo.20581781) (concept · always latest) · v1.0 [10.5281/zenodo.20581782](https://doi.org/10.5281/zenodo.20581782)
**Origin:** Generalized from a finding first reported as `Japan-AISI/aisev` issue #25 (2026-06-03).

---

## Abstract

LLM-as-judge ("grader") components are now standard in evaluation harnesses, including
safety evaluations where a pass/fail verdict gates downstream decisions. A widespread
implicit assumption is that setting the grader's sampling temperature to 0 makes grading
*deterministic* and therefore *reproducible*. This note shows that assumption is wrong on
two levels.

1. **Uncontrolled defaults silently inject randomness.** In a real, publicly released
   evaluation harness (Japan AISI's `aisev`), the grader is invoked without setting
   `temperature` or `seed`. Because the OpenAI provider **omits** a `None` `temperature` from
   the request, the API applies its **default of `1.0`** (not a deterministic default), so the
   grader effectively runs **unseeded at temperature 1.0**. Items near the grader's decision
   boundary then flip pass/fail across otherwise identical runs.

2. **`temperature=0` is necessary but not sufficient.** Pinning the temperature to 0 removes
   the *rare* flips but not the hard ones: the actual grader (`gpt-4o`) still splits **2 of 7**
   items at `temperature=0`, and a Claude (Sonnet 4.6) grader independently reproduces a 2/7
   split. Determinism of the *grader call* is not guaranteed by temperature alone, and the
   effect is not provider-specific.

We provide a small reproduction harness, report measured per-item disagreement rates, and
recommend concrete mitigations: set `temperature=0` explicitly, set a `seed` where the
provider supports it, run multiple `epochs` and **report grader variance instead of a single
point estimate**, and surface a grader-disagreement rate as a harness health metric.

---

## 1. Background

Modern evaluation pipelines increasingly replace human raters with an LLM "judge" that reads
a model transcript and a rubric and emits a verdict (e.g. `correct` / `incorrect`, `pass` /
`fail`). This is convenient and scalable, but it inherits a property practitioners often
forget: **the judge is itself a stochastic model.** If the same transcript can be graded
differently on two runs, then:

- benchmark scores are not reproducible,
- regression detection ("did this model get worse?") is confounded by grader noise, and
- safety gates that depend on a pass/fail threshold can flip for reasons unrelated to the
  model under test.

The common mitigation is "set temperature to 0." This note examines whether that mitigation
is (a) actually applied in practice, and (b) sufficient when it is applied.

## 2. The discovered case: `aisev`

`aisev` is Japan AISI's open-source evaluation environment (Apache-2.0). All references below
are to upstream commit `e0604d1e7997c2949e3cea40d219089dfd477fb4` (`Japan-AISI/aisev` `main`
at 2026-04-16, the merge of PR #23:
<https://github.com/Japan-AISI/aisev/commit/e0604d1e7997c2949e3cea40d219089dfd477fb4>).
**This note does not redistribute aisev source code.** It describes the grader
call path and points to the upstream files by path and commit hash, so each claim is
verifiable against a fixed revision without vendoring any of the harness. Tracing the grader
call path:

1. `scorer_provider.py` calls `model_graded_qa()` **without** passing `temperature` or
   `seed`.
2. This propagates into `inspect_ai`'s `GenerateConfig` with `temperature=None`.
3. The OpenAI provider **omits** a `None` temperature from the API request, so the API applies
   its **default of `1.0`** — full sampling, not deterministic decoding.
4. Net effect: the grader runs **unseeded, at temperature 1.0.**

Nothing in the harness signals to the user that grading is being performed under maximal
sampling noise. The pass/fail numbers *look* like fixed measurements.

## 3. Empirical measurement

**Method.** We hold a fixed set of 7 deliberately borderline question/answer pairs (see
[`src/repro_disagreement_rate.py`](src/repro_disagreement_rate.py)) and grade each item
repeatedly under two configurations: the harness's **default** (`temperature` and `seed` left
unset, so the OpenAI provider omits the parameter and the API applies its default of 1.0 —
N = 20 runs per item) and an explicit **`temperature=0`** (N = 10 runs per item). The grading
prompt and the grade-extraction regex mirror aisev's `get_graded_qa_scorer` and `inspect_ai`'s
default `model_graded_qa` instructions verbatim, so the verdict (`C`/`I`) is parsed exactly as
aisev parses it. We compute the per-item *disagreement rate* — the fraction of runs whose
verdict differs from the item's majority verdict.

**Results — OpenAI `gpt-4o` grader (aisev's default).** Three regimes appear: *stable* (no
disagreement), *rare* (a single flip), and *strong* (near 50/50).

| Item  | default temp, N=20 | `temperature=0`, N=10 | Regime (default) | Disagreement (default) |
|-------|:------------------:|:---------------------:|------------------|:----------------------:|
| item1 | 20 I / 0 C  | 10 I            | stable     | 0.00 |
| item2 | 20 I / 0 C  | 10 I            | stable     | 0.00 |
| item3 | 20 C / 0 I  | 10 C            | stable     | 0.00 |
| item4 | 11 I / 9 C  | **6 I / 4 C**   | **strong** | 0.45 |
| item5 | 19 I / 1 C  | 10 I            | rare       | 0.05 |
| item6 | 12 C / 8 I  | **9 C / 1 I**   | **strong** | 0.40 |
| item7 | 19 C / 1 I  | 10 C            | rare       | 0.05 |

(Grader `gpt-4o`, aisev's default; the exact dated model snapshot was not captured in the run
log. Raw outputs: [`data/repro_raw_openai.json`](data/repro_raw_openai.json).)

Under the default configuration, **4 of 7 items (4, 5, 6, 7) are non-reproducible** — two by a
coin-flip margin (item4, item6) and two by a single flip (item5, item7). For these items the
reported pass/fail is not a property of the answer under test; it is a draw from the grader's
sampling distribution.

Pinning **`temperature=0` helps but does not close the gap.** It stabilises the two *rare*
items (item5 and item7 become unanimous), yet the two *strong* items still flip — item4 splits
6/4 and item6 still yields a dissenting verdict (9/1) over just 10 runs. So on the actual aisev
grader, `temperature=0` reduces non-reproducibility from **4/7 to 2/7**: necessary, but not
sufficient.

## 4. The effect is not provider-specific

A natural objection is that §3 captures a quirk of one provider's grader. It does not. Running
the identical 7-item protocol with a **Claude (Sonnet 4.6)** grader reproduces the same
qualitative picture: 2 of 7 items are non-reproducible at the default temperature, and **still
2 of 7 at `temperature=0`** (item6: 8 I / 2 C; item7: 9 C / 1 I, over 10 runs).[^claude] The
*specific* unstable items differ between graders — OpenAI's `temperature=0` instability falls
on items 4 and 6, Claude's on items 6 and 7 — but the conclusion is identical: pinning the
temperature does not make grading deterministic.

This falsifies the operational belief that `temperature=0 ⇒ deterministic grading`. Residual
non-determinism in production LLM serving can arise from sources unrelated to the sampling
temperature, including:

- batching / request-coalescing effects on the serving side,
- mixture-of-experts routing variability,
- non-associative floating-point reductions across hardware/kernels,
- provider-side load balancing across non-identical model replicas.

The practical consequence: **`temperature=0` reduces, but does not eliminate, grader
disagreement.** Reproducibility must be *measured*, not assumed.

[^claude]: Cross-model check: grader `claude-sonnet-4-6`, same 7-item set, N = 20 at the
default temperature and N = 10 at `temperature=0`. Non-reproducible items were {6, 7} under
both conditions (default — item6 14 I / 6 C, item7 15 C / 5 I; `temperature=0` — item6 8 I /
2 C, item7 9 C / 1 I). The `temperature=0` batch is small and is meant only to show that
disagreement does not vanish, not to estimate a precise rate. Raw outputs:
[`data/repro_raw_anthropic.json`](data/repro_raw_anthropic.json).

## 5. Why this matters

For ordinary capability benchmarks, grader noise inflates variance and can change rankings of
closely-spaced models. For **safety** evaluations the stakes are higher: a pass/fail verdict
near the boundary may gate a deployment decision, a red-team sign-off, or a public claim about
a guardrail's coverage. If that verdict is a coin flip, the evaluation is reporting noise as a
safety property.

## 6. Recommended mitigations

1. **Set `temperature=0` explicitly** at the grader call site. Never rely on the provider's
   `None` default — it may mean `1.0`.
2. **Set `seed`** where the provider supports it, and record it in the run metadata.
3. **Run `epochs > 1`** for the grader and **report variance / a confidence interval**, not a
   single point estimate.
4. **Treat near-boundary items as a first-class signal.** Surface a per-run
   *grader-disagreement rate* as a harness health metric; a high rate means the score is not
   trustworthy regardless of its central value.
5. **Log the effective grader config** (model, temperature, seed) into the results artifact so
   that "what temperature was the judge at?" is answerable after the fact.

## 7. Reproduction

The reproduction harness is [`src/repro_disagreement_rate.py`](src/repro_disagreement_rate.py).
It mirrors aisev's `get_graded_qa_scorer` prompt and `inspect_ai`'s default grade-extraction
verbatim, grades the 7-item set under both the default and `temperature=0` conditions, and
reports the per-item disagreement rate. The raw grader outputs backing §3–§4 are in
[`data/`](data/). See [`README.md`](README.md) for setup and the exact run counts.

## 8. Related work and positioning

**LLM-as-judge reliability.** Using an LLM to score model outputs is now standard practice
(Zheng et al., 2023). Most of this literature characterizes *systematic* biases of the judge —
position bias, verbosity bias, and self-preference (Wang et al., 2023) — that is, skews that
persist *across* runs. The finding here is on an
orthogonal axis: *run-to-run* non-determinism, where the same judge returns different verdicts
for the identical (transcript, rubric) pair on repeated calls. The two concerns are
complementary: a debiased judge can still be irreproducible, and a perfectly reproducible
judge can still be biased.

**Eval-harness grader configuration.** Frameworks such as Inspect AI (UK AISI) expose the
grader as a configurable model call (`model_graded_qa`, `GenerateConfig`), including
`temperature` and, where the provider supports it, `seed`. The gap this note highlights is not
in a framework's capabilities but in its *defaults*: when these knobs are left unset, the
underlying provider may silently sample (OpenAI maps `temperature=None → 1.0`), so a harness
can report grades produced under full sampling noise without ever signalling it. This is a
configuration-level reproducibility hazard, not a modeling one.

**Residual non-determinism at `temperature=0`.** Even under greedy decoding, production LLM
serving is generally not bit-reproducible: request batching, mixture-of-experts routing, and
non-associative floating-point reductions across kernels and hardware can change the argmax
for borderline tokens; recent analysis attributes temperature-0 nondeterminism primarily to a
lack of *batch invariance* in core kernels, where numerics shift with batch size and sequence
slicing (He et al., 2025). The
cross-model check in §4 is consistent with this — a Claude grader at `temperature=0` still
flipped 2/7 items — and motivates the operative recommendation of this note: *measure grader
disagreement; do not assume it away.*

**Pointers.**
- Original report: `Japan-AISI/aisev` issue #25 — *"Reproducibility Improvement Proposal —
  Grader's Pass/Fail Fluctuates Due to Uncontrolled Temperature/Seed."*
  <https://github.com/Japan-AISI/aisev/issues/25>
- Inspect AI (UK AISI): `GenerateConfig`, `model_graded_qa`.

**References.**

1. L. Zheng, W.-L. Chiang, Y. Sheng, et al. "Judging LLM-as-a-Judge with MT-Bench and Chatbot
   Arena." *Advances in Neural Information Processing Systems 36 (NeurIPS 2023), Datasets and
   Benchmarks Track*, 2023. arXiv:2306.05685, DOI: 10.48550/arXiv.2306.05685.
2. P. Wang, L. Li, L. Chen, et al. "Large Language Models are not Fair Evaluators." 2023.
   arXiv:2305.17926, DOI: 10.48550/arXiv.2305.17926.
3. H. He et al. "Defeating Nondeterminism in LLM Inference." Thinking Machines Lab, 2025.
   <https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/>


## Scope of this deposit

To stay within upstream licensing and good-citizen norms, this deposit contains **only the
author's own artifacts**:

- the reproduction harness (`src/`),
- the measured results and their analysis (this note), and
- a written description of the upstream grader call path that references `Japan-AISI/aisev`
  **by file path and commit hash** rather than copying its source.

It does **not** redistribute any portion of the `aisev` codebase. Readers reproduce the
upstream context by checking out the referenced commit of the upstream repository directly.

## Versioning

This artifact follows a two-version plan, archived under a single Zenodo *concept* DOI with a
distinct *version* DOI per release:

- **v1.0 (this release) — report.** Documents the finding and the measured non-determinism
  as of upstream commit `e0604d1` (`main` at 2026-04-16, PR #23), before any fix is adopted.
- **v2.0 (planned) — resolution.** If the proposed mitigations are adopted upstream, v2 will
  add a short "Resolution" section recording the change (the upstream PR / commit and the
  post-fix disagreement rate). Citations to the concept DOI will resolve to the latest
  version; citations to a version DOI remain pinned.

See [`CHANGELOG.md`](CHANGELOG.md).

## Acknowledgments and tooling

The empirical finding, reproduction code, and analysis are the author's own. Drafting of this
note was assisted by an LLM (Claude); all claims and data were verified by the author.

## How to cite

Tamba, H. (2026). *Non-determinism in LLM-as-Judge Graders: An Empirical Reproducibility Note*
(v1.0). Zenodo. https://doi.org/10.5281/zenodo.20581782

- Concept DOI (always resolves to the latest version): [10.5281/zenodo.20581781](https://doi.org/10.5281/zenodo.20581781)
- Version DOI (this release, v1.0): [10.5281/zenodo.20581782](https://doi.org/10.5281/zenodo.20581782)

Machine-readable metadata: [`CITATION.cff`](CITATION.cff).
