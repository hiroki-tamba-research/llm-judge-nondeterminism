"""Run Anthropic-only conditions for v1.1."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from repro_v11_extended import run_condition, ITEMS

all_raw = []
results = []

conditions = [
    ("Claude Sonnet 4.6 temp=0", "anthropic", "claude-sonnet-4-6", 0, None, None),
    ("Claude Opus 4.8 temp=0", "anthropic", "claude-opus-4-8", 0, None, None),
    ("Claude Haiku 4.5 temp=0", "anthropic", "claude-haiku-4-5-20251001", 0, None, None),
    ("Claude Sonnet 4.6 temp=0 top_k=1", "anthropic", "claude-sonnet-4-6", 0, None, 1),
]

R = int(os.environ.get("REPRO_R", "10"))

for label, provider, model, temp, tp, tk in conditions:
    nr, raw = run_condition(label, provider, model, R, temp, tp, tk)
    results.append({"label": label, "nonrepro": nr, "total_items": len(ITEMS), "runs": R})
    all_raw.extend(raw)

print("\n" + "=" * 60)
print("ANTHROPIC SUMMARY")
print("=" * 60)
for r in results:
    label = r["label"]
    nr = r["nonrepro"]
    total = r["total_items"]
    print(f"  {label:45s}  {nr}/{total} non-reproducible")

out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
out = os.path.join(out_dir, "repro_raw_v11_anthropic.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(all_raw, f, ensure_ascii=False, indent=1)
print(f"\nRaw outputs: {out} ({len(all_raw)} calls)")
