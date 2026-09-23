"""A genuinely competent if-then baseline. No AI at all.

It parses the settlement line, looks for reversal references, keyword-matches
the remarks log and normalises names before comparing. Roughly what a good
engineer produces in a day or two. It is deliberately NOT crippled - if the
fine-tuned model cannot beat this, we should find that out here rather than in
front of a bank.
"""
import json, os, re
from schema import CLEAN_ACTION

HERE = os.path.dirname(os.path.abspath(__file__))
FEES = [10.0, 25.0, 50.0]
FEE_TOTALS = {round(f * 1.075, 2) for f in FEES} | {round(f, 2) for f in FEES}

FRAUD_WORDS = re.compile(
    r"onward transfer|fan[- ]out|emptied|moved the funds on|opened this week|"
    r"days old|no other activity|moved on immediately|tranche|newly opened|"
    r"drained|mule|split .*within", re.I)
REVERSAL_WORDS = re.compile(r"\bRV\d{6,}|reversal .*(raised|acknowledg)|"
                            r"refund .*(raised|acknowledg)", re.I)
CREDIT_CONFIRMED = re.compile(
    r"credit posted|confirm(s|ed)? credit|nothing outstanding|value delivered", re.I)
RETRY_WORDS = re.compile(
    r"pressed send again|retried the same|sent twice|one transfer intended|"
    r"app hung", re.I)
DIFFERENT_BENEF = re.compile(r"two different beneficiaries|both authorised|"
                             r"separate instruction", re.I)


def parse_settlement(line):
    if not line:
        return []
    out = []
    for ln in str(line).splitlines():
        parts = ln.split("|")
        if len(parts) >= 4:
            try:
                out.append((float(parts[2]), parts[3].strip()))
            except ValueError:
                pass
    return out


def norm_name(s):
    s = re.sub(r"\b(MR|MRS|MISS|DR)\b", " ", (s or "").upper())
    s = re.sub(r"[^A-Z ]", " ", s)
    return " ".join(sorted(w for w in s.split() if len(w) > 1))


def names_match(a, b):
    na, nb = norm_name(a), norm_name(b)
    if na == nb:
        return True
    wa, wb = set(na.split()), set(nb.split())
    return bool(wa & wb)


def decide(c):
    remarks = " ".join(c.get("remarks") or [])
    complaint = c.get("customer_complaint") or ""
    led = c.get("ledger", [])
    debits = [l for l in led if l["dr_cr"] == "DR"]
    credits = [l for l in led if l["dr_cr"] == "CR"]
    sett = parse_settlement(c.get("settlement_file_line"))
    code = c.get("switch", {}).get("code")
    amt = c["amount_ngn"]

    onward = c.get("onward_transfers") or []
    if len(onward) >= 3 and any(t.get("beneficiary_age_days", 99) <= 7 for t in onward):
        return "SUSPECTED_FRAUD", 0.92, True
    if FRAUD_WORDS.search(remarks):
        return "SUSPECTED_FRAUD", 0.75, True

    if (c.get("reversal") or REVERSAL_WORDS.search(remarks)) and not credits:
        return "REVERSAL_NOT_APPLIED", 0.85, False

    ne = c.get("name_enquiry")
    if ne and not names_match(ne.get("name_returned"), ne.get("name_on_instruction")):
        return "WRONG_BENEFICIARY", 0.85, False

    main_debits = [d for d in debits if abs(d["amount_ngn"] - amt) < 0.01]
    if len(main_debits) >= 2:
        if DIFFERENT_BENEF.search(remarks) or len(sett) >= 2:
            return "NO_BREAK", 0.7, False
        if RETRY_WORDS.search(remarks) or code == "26":
            return "DUPLICATE_POSTING", 0.85, False
        return "DUPLICATE_POSTING", 0.6, True

    if sett:
        s_amt, s_status = sett[0]
        if s_status in ("NIL", "REVERSED_BY_NIBSS"):
            return "SWITCH_TIMEOUT_NO_REVERSAL", 0.8, False
        diff = round(amt - s_amt, 2)
        if abs(diff) > 0.01:
            if round(abs(diff), 2) in FEE_TOTALS or any(
                    abs(abs(diff) - f * 1.075) < 0.02 for f in FEES):
                return "NO_BREAK", 0.75, False
            return "PARTIAL_SETTLEMENT", 0.8, True

    if code in ("09", "91") and not sett:
        return ("SWITCH_TIMEOUT_NO_REVERSAL", 0.6, True) if code == "09" \
            else ("SWITCH_TIMEOUT_NO_REVERSAL", 0.85, False)

    if credits or CREDIT_CONFIRMED.search(remarks) or sett:
        return "NO_BREAK", 0.85, False
    return "NO_BREAK", 0.5, True


def main():
    rows = [json.loads(l) for l in
            open(os.path.join(HERE, "data", "test.jsonl")) if l.strip()]
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(os.path.join(HERE, "out", "preds_rules.jsonl"), "w") as f:
        for r in rows:
            c = json.loads(r["input"])
            b, conf, human = decide(c)
            act = "ESCALATE_FRAUD" if b == "SUSPECTED_FRAUD" else (
                "ESCALATE_MANUAL" if human else CLEAN_ACTION[b])
            f.write(json.dumps({"id": r["id"], "output": {
                "break_type": b, "money_trace": "(rules engine: no narrative)",
                "action": act, "confidence": conf, "needs_human": human,
                "analyst_note": "(rules engine: no note)"}}) + "\n")
    print("wrote out/preds_rules.jsonl")


if __name__ == "__main__":
    main()
