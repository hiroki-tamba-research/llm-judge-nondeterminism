"""
Repro v3 (fidelity-hardened): disagreement rate of aisev's grader, mirroring aisev's
ACTUAL grading prompt + grade extraction.

Verified chain (inspect_ai main 2026-04-16): aisev scorer_provider.py calls
model_graded_qa with NO temperature/seed/config -> inspect_ai forwards no config ->
GenerateConfig temperature=None/seed=None -> OpenAI provider OMITS None temperature ->
API default 1.0, unseeded. So aisev's grader (gpt-4o -> gpt-4o-2024-08-06) samples at
temperature 1.0, unseeded.

Fidelity (matches aisev's get_graded_qa_scorer, so the grader reliably emits a parseable
verdict and we extract it exactly as aisev does):
  - PROMPT  = aisev's get_graded_qa_scorer template + inspect_ai's default model_graded_qa
              instructions (partial_credit=False, "end with GRADE: C/I"), both verbatim.
  - EXTRACT = inspect_ai's DEFAULT_GRADE_PATTERN (last 'GRADE: C/P/I', case-insensitive).

Each borderline item is graded R times at the default (unconfigured) temperature with no
seed -> count items that yield BOTH C and I (non-reproducible). Then at temperature=0.
Raw grader outputs are saved to repro_raw_<provider>.json for free offline re-parsing.

Provider auto-detected: OPENAI_API_KEY -> gpt-4o (faithful to aisev); else ANTHROPIC_API_KEY
-> Claude. Override via REPRO_PROVIDER / REPRO_MODEL. Runs via REPRO_R_DEFAULT / REPRO_R_TEMP0.

Run:
    pip install anthropic openai
    python repro_disagreement_rate.py
"""
import os
import re
import json
from collections import Counter

R_DEFAULT = int(os.environ.get("REPRO_R_DEFAULT", "6"))
R_TEMP0 = int(os.environ.get("REPRO_R_TEMP0", "4"))

ITEMS = [
    {"q": "Explain why the sky appears blue.",
     "c": "Must attribute it to Rayleigh scattering of sunlight by air molecules, with shorter (blue) wavelengths scattered more strongly.",
     "s": "Because sunlight scatters off the atmosphere, and blue light scatters more than red."},
    {"q": "Define recursion in one sentence.",
     "c": "A function (or process) that calls itself, with a base case that stops the recursion.",
     "s": "A function that calls itself."},
    {"q": "Why is 1 not a prime number?",
     "c": "A prime has exactly two distinct positive divisors; 1 has only one, so it fails the definition.",
     "s": "Because it only has one divisor."},
    {"q": "State Newton's second law.",
     "c": "Force equals mass times acceleration (F = ma).",
     "s": "An object's acceleration is proportional to the net force on it and inversely proportional to its mass."},
    {"q": "In one line, what caused the 2008 financial crisis?",
     "c": "The collapse of the US subprime mortgage market and the securitized products built on it, which triggered a banking crisis.",
     "s": "Banks made too many risky home loans that went bad."},
    {"q": "What causes Earth's seasons?",
     "c": "Earth's axial tilt (~23.5 degrees) changes the angle and duration of sunlight through the year; it is NOT due to distance from the Sun.",
     "s": "The Earth is tilted as it goes around the Sun."},
    {"q": "What does HTTP status code 404 mean?",
     "c": "The server could not find the requested resource.",
     "s": "The page doesn't exist."},
]

# inspect_ai default model_graded_qa instructions (partial_credit=False), verbatim.
INSPECT_DEFAULT_INSTRUCTIONS = (
    "After assessing the submitted answer, reply with 'GRADE: $LETTER' (without quotes) "
    "where LETTER is one of CI.  Please choose ONE option for the grade: either \"C\" for "
    "correct answers, or \"I\" for incorrect answers.\n\n"
    "For example, after reviewing a correct answer you might write 'GRADE: C' or after "
    "reviewing an incorrect answer you might write 'GRADE: I'.\n\n"
    "First, write out in a step by step manner your reasoning about the criterion to be "
    "sure that your conclusion is correct. Avoid simply stating the correct answers at the "
    "outset. Then, end with your answer formatted as 'GRADE: $LETTER' (without quotes) "
    "where LETTER is one of CI."
)
# aisev get_graded_qa_scorer template, verbatim ([Task]/[Submission]/[Criterion]).
AISEV_TEMPLATE = (
    "You are assessing a submitted answer on a given task based on a criterion. "
    "Here is the data: [BEGIN DATA] *** [Task]: {q} *** [Submission]: {s} *** "
    "[Criterion]: {c} *** [END DATA] Does the submission meet the criterion? {instructions}"
)
GRADE_PATTERN = r"(?is).*GRADE\s*:\s*([CPI])"   # inspect_ai DEFAULT_GRADE_PATTERN


def _prompt(item):
    return AISEV_TEMPLATE.format(q=item["q"], s=item["s"], c=item["c"],
                                 instructions=INSPECT_DEFAULT_INSTRUCTIONS)


def _extract(text):
    m = re.search(GRADE_PATTERN, text or "")
    return m.group(1).upper() if m else "?"


PROVIDER = os.environ.get("REPRO_PROVIDER") or (
    "openai" if os.environ.get("OPENAI_API_KEY")
    else "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else None)
if PROVIDER is None:
    raise SystemExit("Set OPENAI_API_KEY or ANTHROPIC_API_KEY first.")

_resolved = {"model": None}
_raw = []

if PROVIDER == "openai":
    from openai import OpenAI
    MODEL = os.environ.get("REPRO_MODEL", "gpt-4o")
    _c = OpenAI()

    def _call(item, temperature=None):
        kw = {"temperature": temperature} if temperature is not None else {}
        r = _c.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": _prompt(item)}], **kw)
        _resolved["model"] = getattr(r, "model", None) or _resolved["model"]
        return r.choices[0].message.content
else:
    from anthropic import Anthropic
    MODEL = os.environ.get("REPRO_MODEL", "claude-sonnet-4-6")
    _c = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))  # explicit: avoid SDK picking up an empty OAuth bearer token

    def _call(item, temperature=None):
        kw = {"temperature": temperature} if temperature is not None else {}
        r = _c.messages.create(
            model=MODEL, max_tokens=1024,
            messages=[{"role": "user", "content": _prompt(item)}], **kw)
        _resolved["model"] = getattr(r, "model", None) or _resolved["model"]
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")


def grade(item, idx, cond, temperature=None):
    text = _call(item, temperature=temperature)
    g = _extract(text)
    _raw.append({"item": idx, "cond": cond, "temperature": temperature, "grade": g, "model": _resolved["model"], "raw": text})
    return g


def measure(label, cond, runs, temperature):
    print(f"\n=== {label} (each item x{runs}) ===")
    nonrepro = 0
    for i, item in enumerate(ITEMS, 1):
        grades = [grade(item, i, cond, temperature=temperature) for _ in range(runs)]
        c = Counter(grades)
        flip = len([k for k in c if k in ("C", "I")]) > 1
        nonrepro += int(flip)
        print(f"  item{i}: {dict(c)}{'   <-- FLIPS' if flip else ''}")
    print(f"  => {nonrepro}/{len(ITEMS)} items non-reproducible")
    return nonrepro


if __name__ == "__main__":
    print(f"Grader: {PROVIDER}/{MODEL}  |  {len(ITEMS)} borderline items  |  N_default={R_DEFAULT} N_temp0={R_TEMP0}")
    print("(prompt + extraction mirror aisev's get_graded_qa_scorer / inspect_ai defaults)")
    d = measure("UNCONFIGURED (~API default temp, no seed) = aisev grader condition", "default", R_DEFAULT, None)
    z = measure("temperature=0 (proposed fix)", "temp0", R_TEMP0, 0)
    print(f"\nSummary: default-temp non-reproducible = {d}/{len(ITEMS)};  temp=0 = {z}/{len(ITEMS)}")
    print(f"Resolved model snapshot: {_resolved['model']}")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"repro_raw_{PROVIDER}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(_raw, f, ensure_ascii=False, indent=1)
    print(f"Raw outputs saved: {out}  ({len(_raw)} calls)")
    if PROVIDER == "anthropic":
        print("Grader=Claude (your key). aisev's default grader is gpt-4o; config is identical.")
