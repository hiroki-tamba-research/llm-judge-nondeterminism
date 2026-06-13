"""
v1.1 extended reproduction: top_p / top_k coverage + multi-model scoping.

Adds to v1.0's temperature-only protocol:
  - top_p sweep at temperature=0 (does restricting nucleus sampling help?)
  - Multiple Claude model generations (Sonnet 4.6, Opus 4.8, Haiku 4.5)
  - OpenAI gpt-4o with top_p variations

Run:
    pip install openai anthropic
    export OPENAI_API_KEY=sk-...
    export ANTHROPIC_API_KEY=sk-ant-...
    python src/repro_v11_extended.py
"""
import os
import re
import json
import time
from collections import Counter

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
AISEV_TEMPLATE = (
    "You are assessing a submitted answer on a given task based on a criterion. "
    "Here is the data: [BEGIN DATA] *** [Task]: {q} *** [Submission]: {s} *** "
    "[Criterion]: {c} *** [END DATA] Does the submission meet the criterion? {instructions}"
)
GRADE_PATTERN = r"(?is).*GRADE\s*:\s*([CPI])"

R = int(os.environ.get("REPRO_R", "10"))


def _prompt(item):
    return AISEV_TEMPLATE.format(q=item["q"], s=item["s"], c=item["c"],
                                 instructions=INSPECT_DEFAULT_INSTRUCTIONS)


def _extract(text):
    m = re.search(GRADE_PATTERN, text or "")
    return m.group(1).upper() if m else "?"


def call_openai(item, model, temperature=0, top_p=None):
    from openai import OpenAI
    c = OpenAI()
    kw = {"temperature": temperature}
    if top_p is not None:
        kw["top_p"] = top_p
    r = c.chat.completions.create(
        model=model, messages=[{"role": "user", "content": _prompt(item)}], **kw)
    resolved = getattr(r, "model", model)
    return r.choices[0].message.content, resolved


def call_anthropic(item, model, temperature=0, top_p=None, top_k=None):
    from anthropic import Anthropic
    c = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    kw = {"temperature": temperature}
    if top_p is not None:
        kw["top_p"] = top_p
    if top_k is not None:
        kw["top_k"] = top_k
    r = c.messages.create(
        model=model, max_tokens=1024,
        messages=[{"role": "user", "content": _prompt(item)}], **kw)
    resolved = getattr(r, "model", model)
    text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    return text, resolved


def run_condition(label, provider, model, runs, temperature=0, top_p=None, top_k=None):
    print(f"\n=== {label} | {provider}/{model} | temp={temperature} top_p={top_p} top_k={top_k} | N={runs} ===")
    raw = []
    nonrepro = 0
    for i, item in enumerate(ITEMS, 1):
        grades = []
        for _ in range(runs):
            try:
                if provider == "openai":
                    text, resolved = call_openai(item, model, temperature, top_p)
                else:
                    text, resolved = call_anthropic(item, model, temperature, top_p, top_k)
                g = _extract(text)
                grades.append(g)
                raw.append({"item": i, "label": label, "provider": provider, "model": resolved,
                            "temperature": temperature, "top_p": top_p, "top_k": top_k,
                            "grade": g, "raw": text})
            except Exception as e:
                print(f"  item{i} ERROR: {e}")
                raw.append({"item": i, "label": label, "provider": provider, "model": model,
                            "temperature": temperature, "top_p": top_p, "top_k": top_k,
                            "grade": "ERROR", "raw": str(e)})
                grades.append("ERROR")
            time.sleep(0.2)
        c = Counter(grades)
        flip = len([k for k in c if k in ("C", "I")]) > 1
        nonrepro += int(flip)
        print(f"  item{i}: {dict(c)}{'   <-- FLIPS' if flip else ''}")
    print(f"  => {nonrepro}/{len(ITEMS)} items non-reproducible")
    return nonrepro, raw


if __name__ == "__main__":
    all_raw = []
    results = []

    conditions = [
        # OpenAI: top_p sweep at temp=0
        ("OAI temp=0 (baseline)", "openai", "gpt-4o", 0, None, None),
        ("OAI temp=0 top_p=0.1", "openai", "gpt-4o", 0, 0.1, None),
        ("OAI temp=0 top_p=0.5", "openai", "gpt-4o", 0, 0.5, None),
        # Anthropic: multi-model at temp=0
        ("Claude Sonnet 4.6 temp=0", "anthropic", "claude-sonnet-4-6", 0, None, None),
        ("Claude Opus 4.8 temp=0", "anthropic", "claude-opus-4-8", 0, None, None),
        ("Claude Haiku 4.5 temp=0", "anthropic", "claude-haiku-4-5-20251001", 0, None, None),
        # Anthropic: top_k sweep on Sonnet 4.6
        ("Claude Sonnet 4.6 temp=0 top_k=1", "anthropic", "claude-sonnet-4-6", 0, None, 1),
    ]

    for label, provider, model, temp, tp, tk in conditions:
        key_env = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
        if not os.environ.get(key_env):
            print(f"\nSKIP {label}: {key_env} not set")
            continue
        nr, raw = run_condition(label, provider, model, R, temp, tp, tk)
        results.append({"label": label, "provider": provider, "model": model,
                        "temperature": temp, "top_p": tp, "top_k": tk,
                        "nonrepro": nr, "total_items": len(ITEMS), "runs": R})
        all_raw.extend(raw)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        extras = []
        if r["top_p"] is not None:
            extras.append(f"top_p={r['top_p']}")
        if r["top_k"] is not None:
            extras.append(f"top_k={r['top_k']}")
        extra_str = f" ({', '.join(extras)})" if extras else ""
        print(f"  {r['label']:40s}  {r['nonrepro']}/{r['total_items']} non-reproducible")

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(out_dir, exist_ok=True)

    out_raw = os.path.join(out_dir, "repro_raw_v11_extended.json")
    with open(out_raw, "w", encoding="utf-8") as f:
        json.dump(all_raw, f, ensure_ascii=False, indent=1)
    print(f"\nRaw outputs: {out_raw} ({len(all_raw)} calls)")

    out_summary = os.path.join(out_dir, "repro_summary_v11.json")
    with open(out_summary, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Summary: {out_summary}")
