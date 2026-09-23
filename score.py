"""Mark the model's answers against the known-correct ones.

Built before the model on purpose. The headline number is not accuracy - it is
the fraud miss rate, because that is the error that ends a contract.
"""
import json, sys, os, re
from collections import defaultdict
from schema import BREAKS

HERE = os.path.dirname(os.path.abspath(__file__))
CLOSING = {"AUTO_REVERSE", "MANUAL_CREDIT", "NO_ACTION_SETTLED",
           "RECOVER_FROM_BENEFICIARY"}


def parse(text):
    """Models wrap JSON in prose and code fences. Dig it out; failure to parse
    counts as a wrong answer rather than a crash."""
    if isinstance(text, dict):
        return text
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
    start = t.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(t[start:], start):
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
            continue
        if ch == '"': in_str = True
        elif ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start:i + 1])
                except Exception:
                    return None
    return None


def load(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def report(gold_rows, pred_rows, label):
    gold = {g["id"]: g for g in gold_rows}
    n = len(pred_rows)
    hit_break = hit_action = unparsed = 0
    per = defaultdict(lambda: {"n": 0, "hit": 0})
    confusion = defaultdict(lambda: defaultdict(int))
    fraud_total = fraud_missed = fraud_autoclosed = 0
    defer_should = defer_did = defer_both = 0
    buckets = defaultdict(lambda: {"n": 0, "hit": 0})
    autoclose_n = autoclose_hit = 0

    for p in pred_rows:
        g = gold.get(p["id"])
        if g is None:
            continue
        t = g["target"]
        got = parse(p.get("output"))
        if got is None:
            unparsed += 1
            got = {}
        gb, ga = got.get("break_type"), got.get("action")
        tb, ta = t["break_type"], t["action"]
        per[tb]["n"] += 1
        confusion[tb][gb or "UNPARSEABLE"] += 1
        if gb == tb:
            hit_break += 1; per[tb]["hit"] += 1
        if ga == ta:
            hit_action += 1
        needs = bool(got.get("needs_human"))
        if t["needs_human"]: defer_should += 1
        if needs: defer_did += 1
        if t["needs_human"] and needs: defer_both += 1
        if tb == "SUSPECTED_FRAUD":
            fraud_total += 1
            if gb != "SUSPECTED_FRAUD":
                fraud_missed += 1
                if ga in CLOSING and not needs:
                    fraud_autoclosed += 1
        try:
            conf = float(got.get("confidence", 0))
        except Exception:
            conf = 0.0
        b = min(int(conf * 10) / 10, 0.9)
        buckets[b]["n"] += 1
        if gb == tb: buckets[b]["hit"] += 1
        if not needs:
            autoclose_n += 1
            if gb == tb and ga == ta:
                autoclose_hit += 1

    W = 62
    print("\n" + "=" * W); print(f"  {label}"); print("=" * W)
    print(f"  cases scored          {n}")
    print(f"  unreadable answers    {unparsed}  ({unparsed/max(n,1):.1%})")
    print(f"  break type correct    {hit_break/max(n,1):.1%}")
    print(f"  action correct        {hit_action/max(n,1):.1%}")
    print("\n  -- FRAUD, the number that matters " + "-" * 27)
    if fraud_total:
        print(f"  fraud cases in test   {fraud_total}")
        print(f"  missed (called other) {fraud_missed}  ({fraud_missed/fraud_total:.1%})")
        print(f"  MISSED AND AUTO-CLOSED {fraud_autoclosed}  "
              f"({fraud_autoclosed/fraud_total:.1%})   <-- must be 0")
    print("\n  -- by break type " + "-" * 44)
    for k in BREAKS:
        d = per[k]
        if d["n"]:
            print(f"  {k:<30} {d['hit']:>4}/{d['n']:<4} {d['hit']/d['n']:>7.1%}")
    print("\n  -- handing over to a human " + "-" * 34)
    print(f"  should have deferred   {defer_should}")
    print(f"  actually deferred      {defer_did}")
    if defer_should:
        print(f"  caught                 {defer_both/defer_should:.1%} of the ones it should")
    print(f"  kept and answered      {autoclose_n}, of which correct "
          f"{autoclose_hit/max(autoclose_n,1):.1%}")
    print("\n  -- is its confidence honest? " + "-" * 32)
    for b in sorted(buckets):
        d = buckets[b]
        if d["n"] >= 5:
            print(f"  says {b:.0%}-{b+0.1:.0%} sure   n={d['n']:<5} actually right "
                  f"{d['hit']/d['n']:.1%}")
    print("\n  -- what it confused with what " + "-" * 31)
    for k in BREAKS:
        wrong = {a: cc for a, cc in confusion[k].items() if a != k}
        if wrong:
            top = sorted(wrong.items(), key=lambda kv: -kv[1])[:3]
            print(f"  {k:<30} -> " + ", ".join(f"{a} x{cc}" for a, cc in top))
    print()
    return {"break_acc": hit_break / max(n, 1),
            "fraud_missed": fraud_missed, "fraud_total": fraud_total,
            "fraud_autoclosed": fraud_autoclosed, "unparsed": unparsed}


if __name__ == "__main__":
    gold = load(os.path.join(HERE, "data", "test.jsonl"))
    for path in sys.argv[1:]:
        report(gold, load(path), os.path.basename(path))
