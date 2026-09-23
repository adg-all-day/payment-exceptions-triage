"""Make fake payment-exception cases. Deliberately hard.

Code decides WHAT went wrong, so the correct answer is certain. Agent-written
text supplies the human prose, so the evidence cannot simply be regexed. An
earlier version generated the prose from templates too, and a plain if-then
rules engine scored 96.6% on it - which would have proved nothing.

Realistic difficulty comes from:
  * decisive evidence living in FREE TEXT only (complaint, remarks log)
  * semantic name matching ("C. Okafor" is "Chioma Okafor"; "Musa Bello" is not)
  * amount gaps that are sometimes just a fee plus VAT
  * fraud that does not always arrive with a tidy list of onward transfers
  * one case in ten having two faults, where the graver one is the answer
  * 3% wrong labels in TRAINING only - real analysts under pressure get some
    wrong. The TEST half stays clean, so the score means something.

Nothing here is real. No bank, customer or transaction exists.
"""
import json, random, hashlib, os
from datetime import datetime, timedelta
from schema import BREAKS, ACTIONS, CLEAN_ACTION, CHANNELS, BANKS, RESP
import textpool

SEED = 20260825
N_TOTAL = 5000
N_TEST = 1000
AMBIGUOUS_RATE = 0.12
OVERLAP_RATE = 0.10
TRAIN_LABEL_NOISE = 0.03
HERE = os.path.dirname(os.path.abspath(__file__))

MIX = {
    "NO_BREAK":                   0.26,
    "SWITCH_TIMEOUT_NO_REVERSAL": 0.24,
    "DUPLICATE_POSTING":          0.13,
    "REVERSAL_NOT_APPLIED":       0.12,
    "WRONG_BENEFICIARY":          0.10,
    "PARTIAL_SETTLEMENT":         0.09,
    "SUSPECTED_FRAUD":            0.06,
}
SEVERITY = ["SUSPECTED_FRAUD", "WRONG_BENEFICIARY", "REVERSAL_NOT_APPLIED",
            "DUPLICATE_POSTING", "PARTIAL_SETTLEMENT",
            "SWITCH_TIMEOUT_NO_REVERSAL", "NO_BREAK"]

FIRST = ["Adebayo","Chioma","Ifeanyi","Aisha","Tunde","Ngozi","Yusuf","Folake",
         "Emeka","Halima","Segun","Blessing","Musa","Uche","Kemi","Ibrahim",
         "Amaka","Bolaji","Zainab","Chukwudi","Funmilayo","Sadiq","Oluwaseun",
         "Rukayat","Obinna","Temitope","Abubakar","Ijeoma","Gbenga","Hauwa"]
LAST  = ["Okafor","Adeyemi","Balogun","Mohammed","Eze","Oyelaran","Abubakar",
         "Nwosu","Ogundele","Bello","Chukwu","Adebisi","Sanusi","Okonkwo",
         "Lawal","Iheanacho","Adesanya","Danjuma","Nnamdi","Oluwole"]

NARR = [
    "NIP/{ref}/{frm}/TO {to}",
    "TRF FRM {frm} TO {to} {ref}",
    "{to}/{ref}",
    "MOB TRANSFER TO {to}",
    "NIBSS/{ref}",
    "USSD*737*{to4} TRF {ref}",
]


def nm(r): return f"{r.choice(FIRST)} {r.choice(LAST)}"
def nuban(r): return "".join(str(r.randint(0, 9)) for _ in range(10))
def txn_ref(r): return "REF" + "".join(str(r.randint(0, 9)) for _ in range(12))


def variant_of(r, name):
    """Same human, written differently - what makes name matching a reading
    task rather than a string comparison."""
    a, b = name.split(" ", 1)
    return r.choice([f"{a[0]}. {b}", f"{b} {a}", f"{b}, {a}", name.upper(),
                     f"{a} {b[0]}.", f"{a}  {b}", f"MR {name}", f"{a}-{b}"])


def money(r):
    x = r.random()
    if x < 0.45: return float(r.randrange(500, 50_000, 500))
    if x < 0.85: return float(r.randrange(50_000, 500_000, 1_000))
    return float(r.randrange(500_000, 5_000_000, 10_000))


def leg(eid, when, acct, drcr, amt, narr):
    return {"entry_id": eid, "timestamp": when.isoformat(timespec="seconds"),
            "account": acct, "dr_cr": drcr, "amount_ngn": round(amt, 2),
            "narration": narr}


def base_case(r, idx):
    when = datetime(2026, 7, 1) + timedelta(
        days=r.randint(0, 55), hours=r.randint(6, 21), minutes=r.randint(0, 59))
    amt = money(r)
    bcode = r.choice([k for k in BANKS if k != "035"])
    cust, ben = nm(r), nm(r)
    ca, ba = nuban(r), nuban(r)
    ref = txn_ref(r)
    narr = r.choice(NARR).format(ref=ref, frm=cust.upper(), to=ben.upper(),
                                 to4=ba[:4])
    return {
        "exception_id": f"EXC-2026-{idx:07d}",
        "logged_at": (when + timedelta(minutes=r.randint(20, 900))
                      ).isoformat(timespec="seconds"),
        "value_date": when.date().isoformat(),
        "channel": r.choices(CHANNELS, weights=[52, 22, 12, 9, 5])[0],
        "amount_ngn": round(amt, 2),
        "customer": {"account": ca, "name": cust},
        "beneficiary": {"account": ba, "name_on_instruction": ben,
                        "bank_code": bcode, "bank": BANKS[bcode]},
        "session_id": "0000" + when.strftime("%d%m%y%H%M%S") + "".join(
            str(r.randint(0, 9)) for _ in range(12)),
        "transaction_ref": ref,
        "ledger": [leg("L1", when, ca, "DR", amt, narr)],
        "switch": {"code": "00", "message": RESP["00"],
                   "at": (when + timedelta(seconds=r.randint(2, 40))
                          ).isoformat(timespec="seconds")},
        "settlement_file_line": f"{when.date().isoformat()}|{ref}|{amt:.2f}|SETTLED",
        "customer_complaint": None,
        "remarks": [],
        "onward_transfers": [],
        "_w": when, "_ref": ref,
    }


# -------------------------------------------------------------------- faults

def f_no_break(r, c):
    w, amt = c["_w"], c["amount_ngn"]
    style = r.random()
    if style < 0.30:
        c["remarks"].append(
            f"called {c['beneficiary']['bank']} recon desk, they confirm credit "
            f"posted their side. nothing outstanding on our end.")
    elif style < 0.62:
        c["ledger"].append(leg("L2", w + timedelta(minutes=r.randint(3, 180)),
                               c["beneficiary"]["account"], "CR", amt,
                               "NIP INWARD " + c["_ref"]))
    else:
        r2 = txn_ref(r)
        c["ledger"].append(leg("L3", w + timedelta(minutes=r.randint(8, 240)),
                               c["customer"]["account"], "DR", amt,
                               r.choice(NARR).format(
                                   ref=r2, frm=c["customer"]["name"].upper(),
                                   to=nm(r).upper(), to4=nuban(r)[:4])))
        c["settlement_file_line"] = (f"{c['value_date']}|{c['_ref']}|{amt:.2f}|SETTLED\n"
                                     f"{c['value_date']}|{r2}|{amt:.2f}|SETTLED")
        c["remarks"].append("customer says double debit. checked - two different "
                            "beneficiaries, both authorised by her.")
    return ("Debit posted and the funds reached the beneficiary. Settlement "
            "agrees with the ledger. Nothing to reverse.",
            "Confirmed settled. No action required.")


def f_timeout(r, c):
    c["switch"]["code"] = r.choice(["09", "91"])
    c["switch"]["message"] = RESP[c["switch"]["code"]]
    c["settlement_file_line"] = r.choice([
        None, f"{c['value_date']}|{c['_ref']}|0.00|NIL",
        f"{c['value_date']}|{c['_ref']}|{c['amount_ngn']:.2f}|REVERSED_BY_NIBSS",
        None])
    return ("Customer was debited. The switch never confirmed and no credit "
            "reached the beneficiary. The funds never left the bank and the "
            "automatic reversal did not fire.",
            "No settlement. Reversed to customer and closed.")


def f_duplicate(r, c):
    w = c["_w"]
    same_sid = r.random() < 0.65
    c["ledger"].append(leg("L2", w + timedelta(seconds=r.randint(2, 120)),
                           c["customer"]["account"], "DR", c["amount_ngn"],
                           c["ledger"][0]["narration"] if same_sid else
                           r.choice(NARR).format(
                               ref=c["_ref"], frm=c["customer"]["name"].upper(),
                               to=c["beneficiary"]["name_on_instruction"].upper(),
                               to4=c["beneficiary"]["account"][:4])))
    if not same_sid:
        c["remarks"].append(r.choice([
            "customer says app hung and she pressed send again.",
            "network was slow, customer retried the same transfer.",
            "confirmed with customer: one transfer intended, sent twice."]))
    c["switch"]["code"] = "26"; c["switch"]["message"] = RESP["26"]
    c["settlement_file_line"] = (f"{c['value_date']}|{c['_ref']}|"
                                 f"{c['amount_ngn']:.2f}|SETTLED")
    return ("Two debits for one instruction, but settlement shows only one leg "
            "went out. The second debit is internal duplication.",
            "Duplicate posting. Reversed the extra leg.")


def f_reversal_missing(r, c):
    w = c["_w"]
    c["switch"]["code"] = "91"; c["switch"]["message"] = RESP["91"]
    c["settlement_file_line"] = None
    rv = "RV" + "".join(str(r.randint(0, 9)) for _ in range(10))
    if r.random() < 0.55:
        c["remarks"].append(f"reversal {rv} raised and acknowledged by NIBSS.")
    else:
        c["reversal"] = {"reference": rv, "acknowledged": True,
                         "raised_at": (w + timedelta(hours=r.randint(1, 20))
                                       ).isoformat(timespec="seconds")}
    return ("A reversal was raised and acknowledged but never posted to the "
            "customer's account. There is no credit leg.",
            f"Reversal {rv} acknowledged but unposted. Credited manually.")


def f_wrong_beneficiary(r, c):
    w = c["_w"]
    actual = nuban(r)
    c["ledger"].append(leg("L2", w + timedelta(seconds=r.randint(5, 120)),
                           actual, "CR", c["amount_ngn"], "NIP INWARD " + c["_ref"]))
    c["name_enquiry"] = {
        "account_queried": c["beneficiary"]["account"],
        "name_returned": nm(r),
        "name_on_instruction": c["beneficiary"]["name_on_instruction"]}
    return ("The credit posted to an account whose name does not match the "
            "person on the instruction. The money is with the wrong party.",
            f"Wrong beneficiary. Recall raised against {c['beneficiary']['bank']}.")


def f_partial(r, c):
    short = round(c["amount_ngn"] * r.uniform(0.03, 0.4), 2)
    c["settlement_file_line"] = (f"{c['value_date']}|{c['_ref']}|"
                                 f"{c['amount_ngn'] - short:.2f}|SETTLED")
    if r.random() < 0.35:
        c["remarks"].append("difference does not correspond to any charge. "
                            "raised with NIBSS.")
    return (f"Ledger and settlement disagree by {short:,.2f} and the difference "
            "is not a fee. Which record is correct cannot be decided here.",
            f"Unexplained shortfall of {short:,.2f}. Referred to settlement ops.")


def f_fee_not_a_break(r, c):
    """Amounts differ, but only by the charge and its VAT. A rules engine
    comparing two numbers calls this a break. It is not."""
    fee = 10.0 if c["amount_ngn"] <= 5000 else (25.0 if c["amount_ngn"] <= 50000 else 50.0)
    vat = round(fee * 0.075, 2)
    c["settlement_file_line"] = (f"{c['value_date']}|{c['_ref']}|"
                                 f"{c['amount_ngn'] - fee - vat:.2f}|SETTLED")
    c["ledger"].append(leg("L2", c["_w"] + timedelta(seconds=30),
                           c["customer"]["account"], "DR", fee + vat,
                           f"NIP CHG {fee:.2f} + VAT {vat:.2f}"))
    return (f"Settlement is lower than the ledger by exactly the transfer charge "
            f"of {fee:,.2f} plus VAT of {vat:,.2f}. That is a fee, not a shortfall.",
            "Difference is the standard charge and VAT. Not a break.")


def f_name_variant_ok(r, c):
    """Name enquiry returned a DIFFERENT SPELLING of the same person."""
    w = c["_w"]
    ben = c["beneficiary"]["name_on_instruction"]
    c["ledger"].append(leg("L2", w + timedelta(seconds=r.randint(5, 90)),
                           c["beneficiary"]["account"], "CR", c["amount_ngn"],
                           "NIP INWARD " + c["_ref"]))
    c["name_enquiry"] = {"account_queried": c["beneficiary"]["account"],
                         "name_returned": variant_of(r, ben),
                         "name_on_instruction": ben}
    return ("The name returned is a different spelling of the same person, and "
            "the credit posted to the account that was queried. Correct.",
            "Name variant of the same beneficiary. No action.")


def f_fraud(r, c):
    w = c["_w"]
    c["ledger"].append(leg("L2", w + timedelta(seconds=r.randint(3, 45)),
                           c["beneficiary"]["account"], "CR", c["amount_ngn"],
                           "NIP INWARD " + c["_ref"]))
    tidy = r.random() < 0.45
    n = r.randint(3, 7)
    if tidy:
        share = c["amount_ngn"] / n
        for _ in range(n):
            c["onward_transfers"].append({
                "at": (w + timedelta(minutes=r.randint(1, 25))).isoformat(timespec="seconds"),
                "from_account": c["beneficiary"]["account"],
                "to_account": nuban(r), "to_bank": BANKS[r.choice(list(BANKS))],
                "amount_ngn": round(share * r.uniform(0.8, 1.15), 2),
                "beneficiary_age_days": r.randint(0, 6)})
    else:
        c["remarks"].append(r.choice([
            f"beneficiary account emptied within {r.randint(6,40)} minutes across "
            f"{n} onward transfers, all to accounts opened this week.",
            f"receiving account is {r.randint(1,9)} days old and has already moved "
            f"the funds on in {n} tranches.",
            f"funds moved on immediately to {n} different banks. account opened "
            f"{r.randint(0,5)} days ago, no other activity."]))
    return (f"Funds were credited then split across {n} onward transfers to newly "
            "opened accounts. The customer denies authorising it. This is a "
            "fan-out pattern, not a settlement fault.",
            f"Fan-out to {n} new accounts. Frozen and referred to fraud desk.")


FAULTS = {
    "NO_BREAK": f_no_break,
    "SWITCH_TIMEOUT_NO_REVERSAL": f_timeout,
    "DUPLICATE_POSTING": f_duplicate,
    "REVERSAL_NOT_APPLIED": f_reversal_missing,
    "WRONG_BENEFICIARY": f_wrong_beneficiary,
    "PARTIAL_SETTLEMENT": f_partial,
    "SUSPECTED_FRAUD": f_fraud,
}
NO_BREAK_STYLES = [(f_no_break, 0.55), (f_fee_not_a_break, 0.22),
                   (f_name_variant_ok, 0.23)]


def apply_fault(r, c, kind):
    if kind == "NO_BREAK":
        fns, ws = zip(*NO_BREAK_STYLES)
        return r.choices(fns, weights=ws)[0](r, c)
    return FAULTS[kind](r, c)


def make_ambiguous(r, c, trace):
    """Remove the deciding evidence, so the only right answer is: ask a human."""
    gone = []
    if c.get("settlement_file_line") is not None and r.random() < 0.7:
        c["settlement_file_line"] = None
        gone.append("the settlement file line for this session is missing")
    if r.random() < 0.6:
        c["switch"]["code"] = "09"; c["switch"]["message"] = RESP["09"]
        gone.append("the switch never returned a final response")
    if len(c["ledger"]) > 1 and r.random() < 0.55:
        c["ledger"] = c["ledger"][:1]
        gone.append("the second ledger leg is not on this extract")
    if c.get("remarks") and r.random() < 0.5:
        c["remarks"] = []
        gone.append("the remarks log is empty")
    if not gone:
        c["switch"]["code"] = "09"; c["switch"]["message"] = RESP["09"]
        gone.append("the switch never returned a final response")
    # Keep the whole trace. An earlier version chopped it at the first full
    # stop, which left stubs like "Sequence matters here." followed by the
    # caveat - a fragment that reasons about nothing.
    return (trace.rstrip(". ") + ". However " + ", and ".join(gone) +
            ". There is not enough here to decide, and guessing either way risks "
            "double-refunding or leaving the customer short.",
            "Insufficient evidence - " + gone[0] + ". Referred for manual "
            "investigation.")


INSTRUCTION = (
    "You are a payments exceptions analyst at a Nigerian bank. Read the case "
    "and reply with JSON only, using exactly these keys: break_type, "
    "money_trace, action, confidence, needs_human, analyst_note.\n"
    "break_type must be one of: " + ", ".join(BREAKS) + ".\n"
    "action must be one of: " + ", ".join(ACTIONS) + ".\n"
    "confidence is a number between 0 and 1. needs_human is true or false."
)


def build(idx, r, pools=None):
    kinds = list(MIX)
    kind = r.choices(kinds, weights=[MIX[k] for k in kinds])[0]
    c = base_case(r, idx)
    trace, note = apply_fault(r, c, kind)

    # One case in ten has a second thing wrong; the graver one is the answer.
    if r.random() < OVERLAP_RATE:
        other = r.choice([k for k in FAULTS if k not in (kind, "NO_BREAK")])
        t2, n2 = FAULTS[other](r, c)
        if SEVERITY.index(other) < SEVERITY.index(kind):
            kind, trace, note = other, t2, n2

    if pools is not None and pools.inp:
        textpool.dress(pools, c, kind, r, c["_w"])
        a_trace, a_note = textpool.analyst(pools, c, kind, r)
        if a_trace:
            trace, note = a_trace, a_note

    action = CLEAN_ACTION[kind]
    amb = False
    if kind not in ("NO_BREAK", "SUSPECTED_FRAUD") and r.random() < AMBIGUOUS_RATE:
        trace, note = make_ambiguous(r, c, trace)
        action, amb = "ESCALATE_MANUAL", True

    conf = round(r.uniform(0.52, 0.70), 2) if amb else round(r.uniform(0.86, 0.99), 2)
    for k in ("_w", "_ref"):
        c.pop(k, None)
    c["remarks"] = c["remarks"] or None

    return {"id": c["exception_id"], "ambiguous": amb, "true_break": kind,
            "instruction": INSTRUCTION,
            "input": json.dumps(c, indent=1, sort_keys=True),
            "target": {"break_type": kind, "money_trace": trace, "action": action,
                       "confidence": conf,
                       "needs_human": amb or action.startswith("ESCALATE"),
                       "analyst_note": note}}


def add_label_noise(rows, r, rate):
    """Real analysts get some wrong. Train on that. Never the test set - the
    test set is the ruler and must stay straight."""
    n = 0
    for row in rows:
        if r.random() < rate:
            wrong = r.choice([k for k in BREAKS if k != row["target"]["break_type"]])
            row["target"]["break_type"] = wrong
            row["target"]["action"] = CLEAN_ACTION[wrong]
            n += 1
    return n


def main():
    r = random.Random(SEED)
    pools = textpool.Pools()
    if not pools.ready():
        print(f"WARNING: {len(pools.inp)}/7 input and {len(pools.out)}/7 output "
              f"text pools - falling back to templates for the rest")
    rows = [build(i + 1, r, pools) for i in range(N_TOTAL)]
    r.shuffle(rows)
    test, train = rows[:N_TEST], rows[N_TEST:]
    noisy = add_label_noise(train, r, TRAIN_LABEL_NOISE)

    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    for name, part in (("train", train), ("test", test)):
        with open(os.path.join(HERE, "data", f"{name}.jsonl"), "w") as f:
            for row in part:
                f.write(json.dumps(row) + "\n")

    counts = {}
    for row in rows:
        counts[row["true_break"]] = counts.get(row["true_break"], 0) + 1
    amb = sum(1 for row in rows if row["ambiguous"])
    print(f"train {len(train)}  test {len(test)}")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<30} {v:>5}  {v/len(rows):6.1%}")
    print(f"  {'(ambiguous, must defer)':<30} {amb:>5}  {amb/len(rows):6.1%}")
    print(f"  {'(train labels deliberately wrong)':<30} {noisy:>5}")
    fp = hashlib.sha1(open(os.path.join(HERE, "data", "train.jsonl"), "rb"
                           ).read()).hexdigest()[:12]
    print("train fingerprint", fp)


if __name__ == "__main__":
    main()
