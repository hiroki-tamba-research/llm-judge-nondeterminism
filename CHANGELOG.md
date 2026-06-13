# Changelog

All notable changes to this artifact. Each released version is archived on Zenodo with its
own version DOI under a single concept DOI.

## [1.1] - 2026-06-13

### Extended parameter coverage
- **`top_p` sweep** (OpenAI `gpt-4o`, temp=0): top_p ∈ {default, 0.1, 0.5} all produce
  2/7 non-reproducible items (same items 4 and 6). `top_p` is not a mitigation.
- **Multi-model check** (Anthropic, temp=0): Sonnet 4.6 and Haiku 4.5 both show 1/7
  (item 6). Non-determinism is model-tier-independent within a provider.
- **`top_k=1` forced greedy** (Sonnet 4.6, temp=0): still 1/7 (item 6, 8 I / 2 C).
  Forced greedy decoding does not eliminate the flips, confirming the instability
  originates before the sampling step.
- **Opus 4.8 `temperature` deprecated**: API rejects `temperature` with HTTP 400.
  The "set `temperature=0`" recommendation is already inapplicable to this model.
- **Contributor credit**: Eirik Botten Nicolaysen (avalyset / EcoDeco AS) for
  independent verification and observations on top_p/top_k/cross-model scoping.
- New data files: `data/repro_raw_v11_extended.json` (210 OpenAI calls),
  `data/repro_raw_v11_anthropic.json` (280 Anthropic calls).
- New scripts: `src/repro_v11_extended.py`, `src/run_anthropic_v11.py`.
- License: prose upgraded to CC-BY-NC-ND-4.0 (code remains MIT).

## [1.0] - 2026-06-07

### Report (pre-resolution)
- Initial deposit: reproduction harness, measured per-item grader disagreement rates, and the
  technical note.
- Documents non-determinism in the `aisev` grader as of upstream commit `e0604d1` (`main` at 2026-04-16, PR #23)
  (uncontrolled `temperature`/`seed`; OpenAI `temperature=None → 1.0`).
- On the actual aisev grader (`gpt-4o`), `temperature=0` reduces non-reproducibility from
  **4/7 to 2/7** items (items 4 and 6 still flip): necessary, but not sufficient.
- Cross-model check: a Claude (Sonnet 4.6) grader independently reproduces a 2/7 split at
  `temperature=0` (items 6 and 7).
- Includes raw grader outputs (`data/repro_raw_openai.json`, `data/repro_raw_anthropic.json`)
  as the evidence behind §3–§4.
- Generalized from `Japan-AISI/aisev` issue #25 (2026-06-03).
- Zenodo: version DOI 10.5281/zenodo.20581782, concept DOI 10.5281/zenodo.20581781.

## [2.0] - planned

### Resolution (if the fix is adopted upstream)
- Add a "Resolution" section recording the upstream PR/commit that adopts the mitigations.
- Report the post-fix disagreement rate for comparison against the v1.0 baseline.
