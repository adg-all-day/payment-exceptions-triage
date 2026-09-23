"""How often does the written explanation cite evidence the case does not contain?

A wrong classification is a mistake. A confidently fabricated reference number in
an audit trail is a different kind of problem, so it is worth measuring on its
own rather than folding into accuracy.
"""
import json, re, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
gold = {json.loads(l)["id"]: json.loads(l) for l in
        open(os.path.join(HERE, "data/test.jsonl"))}

sys.path.insert(0, HERE)
from score import parse   # reuse the scorer's parser so the sample matches

REF = re.compile(r"\b(?:REF|RV)[0-9]{6,}\b")
AMT = re.compile(r"\b\d{1,3}(?:,\d{3})+(?:\.\d{2})?\b")

def audit(path):
    rows = [json.loads(l) for l in open(path)]
    n = bad_ref = bad_amt = either = 0
    for r in rows:
        a = parse(r["output"]); g = gold.get(r["id"])
        if a is None or g is None: continue
        case = g["input"]
        trace = " ".join(str(a.get(k, "")) for k in ("money_trace", "analyst_note"))
        n += 1
        # a reference the case never mentions
        br = [x for x in set(REF.findall(trace)) if x not in case]
        # an amount the case never mentions (ignore bare integers, too noisy)
        ba = [x for x in set(AMT.findall(trace))
              if x not in case and x.replace(",", "") not in case]
        if br: bad_ref += 1
        if ba: bad_amt += 1
        if br or ba: either += 1
    return n, bad_ref, bad_amt, either

print(f"{'':34}{'cited a ref':>13}{'cited an amt':>14}{'either':>10}")
print(f"{'':34}{'not in case':>13}{'not in case':>14}{'':>10}")
print("-" * 72)
for f, lab in [("artifacts/out/preds_tuned.jsonl", "Gemma 4 E2B, fine-tuned"),
               ("artifacts/out/preds_26b.jsonl", "Gemma 4 26B, untrained"),
               ("artifacts/out/preds_base.jsonl", "Gemma 4 E2B, untrained")]:
    p = os.path.join(HERE, f)
    if not os.path.exists(p): continue
    n, br, ba, ei = audit(p)
    print(f"  {lab:<32}{br/n:>12.1%}{ba/n:>14.1%}{ei/n:>10.1%}   (n={n})")
