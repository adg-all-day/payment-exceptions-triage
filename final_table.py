"""One scoreboard, five systems, same 1000 unseen cases."""
import io, contextlib, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import load, report

HERE = os.path.dirname(os.path.abspath(__file__))
gold = load(os.path.join(HERE, "data", "test.jsonl"))
NAMES = [("preds_rules", "1  rules engine, no AI"),
         ("preds_base", "2  Gemma 4 E2B, untrained"),
         ("preds_26b", "3  Gemma 4 26B, untrained"),
         ("preds_tuned", "4  Gemma 4 E2B, FINE-TUNED"),
         ("preds_tuned_gated", "5  fine-tuned + safety gate")]
PATS = [r"break type correct\s+([0-9.]+%)",
        r"action correct\s+([0-9.]+%)",
        r"missed \(called other\) \d+\s+\(([0-9.]+%)\)",
        r"MISSED AND AUTO-CLOSED \d+\s+\(([0-9.]+%)\)",
        r"unreadable answers\s+\d+\s+\(([0-9.]+%)\)"]
W = 80
print("=" * W)
print("  %-30s%8s%9s%9s%9s%9s" % ("SYSTEM", "break", "action", "fraud", "AUTO-", "unread"))
print("  %-30s%8s%9s%9s%9s%9s" % ("", "type", "", "missed", "CLOSED", "able"))
print("-" * W)
for f, label in NAMES:
    p = os.path.join(HERE, "out", f + ".jsonl")
    if not os.path.exists(p):
        print("  %-30s  (not run)" % label); continue
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        report(gold, load(p), f)
    t = buf.getvalue()
    vals = []
    for pat in PATS:
        m = re.search(pat, t)
        vals.append(m.group(1) if m else "-")
    print("  %-30s%8s%9s%9s%9s%9s" % tuple([label] + vals))
print("=" * W)
print("  Lower is better for the last three columns. AUTO-CLOSED must be 0.")
