# Changelog

All notable changes to this artifact. Each released version is archived on Zenodo with its
own version DOI under a single concept DOI.

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

## [2.0] - planned

### Resolution (if the fix is adopted upstream)
- Add a "Resolution" section recording the upstream PR/commit that adopts the mitigations.
- Report the post-fix disagreement rate for comparison against the v1.0 baseline.
