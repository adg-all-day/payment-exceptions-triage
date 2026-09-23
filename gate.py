"""A hard safety gate that sits after the model.

The fine-tuned model still auto-closes 38% of fraud. No amount of "the model is
usually right" makes that sellable to a bank, and it should not be fixed by
hoping a bigger model is better. It is fixed by making the dangerous action
impossible.

The rule: if ANY fraud signal is present in the case - money moving onward fast,
brand-new receiving accounts, or a customer denying they authorised it - the
system may not close the case, whatever the model concluded. It escalates.

This deliberately over-escalates. Some perfectly ordinary cases will go to a
human because the customer used the words "I did not authorise this". That is
the correct trade: a wasted review costs minutes, a missed fraud costs the
relationship. The cost of the trade is measured below rather than assumed.

    python3 gate.py out/preds_tuned.jsonl out/preds_tuned_gated.jsonl
"""
import json, re, sys, os
from score import parse

HERE = os.path.dirname(os.path.abspath(__file__))
CLOSING = {"AUTO_REVERSE", "MANUAL_CREDIT", "NO_ACTION_SETTLED",
           "RECOVER_FROM_BENEFICIARY"}

# Money behaving like laundered money, described however the writer described it.
MOVEMENT = re.compile(
    r"onward transfer|fan[- ]out|emptied|moved the funds on|moved on immediately|"
    r"tranche|opened this week|days old|no other activity|drained|"
    r"split .{0,20}within|newly opened|no other activity", re.I)

# The customer saying, in any of the ways people say it, "this was not me".
DENIAL = re.compile(
    r"did not (authorise|authorize|make|do|send|initiate)|didn'?t (authorise|authorize|make|do)|"
    r"not (mine|me)\b|never (made|sent|did|authorised|authorized|initiated)|"
    r"someone (accessed|took|has taken)|unauthorised|unauthorized|"
    r"i know nothing about|do not recognise|don'?t recognise|"
    r"i was (at work|asleep|in a meeting)|phone was with me|"
    r"i did not (share|give) my (pin|otp)|block my account|freeze my account|"
    r"otp i did not request", re.I)


def fraud_signal(case):
    """Return the reason this case must not be auto-closed, or None."""
    onward = case.get("onward_transfers") or []
    if len(onward) >= 2 and any(t.get("beneficiary_age_days", 99) <= 14
                                for t in onward):
        return f"{len(onward)} onward transfers to accounts under 14 days old"
    if len(onward) >= 3:
        return f"{len(onward)} onward transfers"
    remarks = " ".join(case.get("remarks") or [])
    if MOVEMENT.search(remarks):
        return "remarks describe funds moving onward to new accounts"
    if DENIAL.search(case.get("customer_complaint") or ""):
        return "customer denies authorising the transfer"
    if DENIAL.search(remarks):
        return "file records the customer denying the transfer"
    return None


def apply_gate(pred_out, case):
    """Never downgrade. Only ever escalate."""
    d = parse(pred_out)
    if d is None:
        # If we cannot read the answer at all, a human definitely looks at it.
        return {"break_type": "SUSPECTED_FRAUD", "money_trace": "(unreadable "
                "model output - gated to a human)", "action": "ESCALATE_MANUAL",
                "confidence": 0.0, "needs_human": True,
                "analyst_note": "Model output could not be parsed."}, "unreadable"
    why = fraud_signal(case)
    if why and d.get("action") in CLOSING:
        d = dict(d)
        d["action"] = "ESCALATE_FRAUD"
        d["needs_human"] = True
        d["analyst_note"] = (f"HELD BY SAFETY GATE: {why}. Model proposed "
                             f"closing this. Not permitted.\n"
                             + str(d.get("analyst_note", "")))
        return d, why
    if why:
        d = dict(d); d["needs_human"] = True
        return d, why
    return d, None


def main(src, dst):
    cases = {json.loads(l)["id"]: json.loads(json.loads(l)["input"])
             for l in open(os.path.join(HERE, "data", "test.jsonl")) if l.strip()}
    held = 0
    rows = [json.loads(l) for l in open(src) if l.strip()]
    with open(dst, "w") as f:
        for r in rows:
            case = cases.get(r["id"])
            if case is None:
                f.write(json.dumps(r) + "\n"); continue
            d, why = apply_gate(r.get("output"), case)
            if why:
                held += 1
            f.write(json.dumps({"id": r["id"], "output": d}) + "\n")
    print(f"{os.path.basename(src)} -> {os.path.basename(dst)}   "
          f"gate held {held}/{len(rows)} ({held/len(rows):.1%}) for a human")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
