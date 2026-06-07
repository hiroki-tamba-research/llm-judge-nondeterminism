# Non-determinism in LLM-as-Judge Graders

An empirical reproducibility note plus a reproduction harness, showing that
LLM-as-judge graders are non-deterministic — and that the common
`temperature=0` fix is **necessary but not sufficient**.

- **The note:** [`NOTE.md`](NOTE.md) — read this first.
- **PDF:** [`NOTE.pdf`](NOTE.pdf) — rendered from `NOTE.md` via [`tools/render_pdf.py`](tools/render_pdf.py) (`pip install markdown xhtml2pdf`).
- **Reproduction:** [`src/repro_disagreement_rate.py`](src/repro_disagreement_rate.py)
- **Origin:** generalized from [`Japan-AISI/aisev` issue #25](https://github.com/Japan-AISI/aisev/issues/25).

## What this deposit contains (and does not)

Contains **only the author's own artifacts**: the reproduction harness, the measured results,
and a writeup that references the upstream grader call path **by file path and commit hash**.
It does **not** redistribute any of the `aisev` codebase — reproduce the upstream context by
checking out the referenced commit of the upstream repo directly. See *Scope of this deposit*
in [`NOTE.md`](NOTE.md).

## TL;DR

1. A real eval harness (`aisev`) calls its grader without setting `temperature`
   or `seed`. The OpenAI provider maps `temperature=None → 1.0`, so the grader
   runs **unseeded at temperature 1.0** and near-boundary items flip pass/fail.
2. Even at `temperature=0`, a Claude grader still flipped on **2 of 7** items.
   Reproducibility must be *measured*, not assumed.

## Reproduce

```bash
python -m venv .venv && . .venv/Scripts/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# OpenAI gpt-4o grader (faithful to aisev's default): N=20 default + N=10 at temperature=0
export OPENAI_API_KEY=sk-...                        # PowerShell: $env:OPENAI_API_KEY="sk-..."
REPRO_R_DEFAULT=20 REPRO_R_TEMP0=10 python src/repro_disagreement_rate.py

# Cross-model check with Claude (Sonnet 4.6)
export ANTHROPIC_API_KEY=sk-ant-...
REPRO_PROVIDER=anthropic REPRO_R_DEFAULT=20 REPRO_R_TEMP0=10 python src/repro_disagreement_rate.py
```

The script mirrors aisev's `get_graded_qa_scorer` prompt and `inspect_ai`'s default
grade-extraction verbatim, auto-detects the provider from whichever API key is set (override
with `REPRO_PROVIDER` / `REPRO_MODEL`), and runs **both** the default and `temperature=0`
conditions — printing per-item verdict counts and saving raw grader outputs to
`repro_raw_<provider>.json`. The raw evidence behind §3–§4 is committed under [`data/`](data/).

## Getting a DOI (Zenodo + GitHub)

This repo is set up so a GitHub Release mints a citable DOI automatically.

1. Push this repo to GitHub (public).
2. Sign in to <https://zenodo.org> with GitHub, open **Settings → GitHub**, and flip
   this repository's switch to **On**.
3. Back on GitHub, create a **Release** (e.g. tag `v1.0`). Zenodo archives the
   release zip and mints a DOI.
4. Zenodo reads [`.zenodo.json`](.zenodo.json) for the title, authors, license, and
   related identifiers — edit that file (ORCID, affiliation) before releasing.
5. Add the **concept DOI** badge to this README and the DOI to `CITATION.cff`, then
   cross-link it from the aisev issue.

**Versioning:** release **v1.0** now (the report). If the fix is adopted upstream, cut a
**v2.0** release adding the resolution — Zenodo mints a new *version DOI* under the same
*concept DOI*. Cite the concept DOI to always resolve to the latest; cite a version DOI to
pin. See [`CHANGELOG.md`](CHANGELOG.md).

> Note: Zenodo's GitHub integration archives a **release snapshot of the repo**, not
> the GitHub issue. That is exactly why we publish the generalized note here rather
> than trying to "DOI an issue."

## License

- Code (`src/`): MIT — see [`LICENSE`](LICENSE).
- Prose (`NOTE.md` and this README): CC-BY-4.0.
