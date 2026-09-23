"""Swap templated prose for the human-sounding text the agents wrote.

Two things matter beyond nicer sentences.

1. CROSS-MIXING. If every fraud case carried a complaint from the fraud pool,
   the model would learn the pool, not the evidence - and so would a regex. So a
   third of the time the complaint comes from a DIFFERENT fault's pool. That is
   realistic: a customer describes symptoms and rarely knows what went wrong.

2. SAFE DISTRACTORS. Remarks often DO carry the deciding fact, so they cannot be
   mixed freely - a fraud remark dropped onto a timeout case would change what
   the right answer is. Only content-free chatter is borrowed across pools.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT = os.path.join(HERE, "data", "text")

# The user asked for no Pidgin. A few slipped through; drop those lines.
PIDGIN = re.compile(
    r"\b(abeg|dey|wetin|sabi|wahala|na so|no be|make i|e don|don go|don short|"
    r"check am|i been|shey|oga|comot|waka)\b", re.I)

# Lines that assert the case is fine. These must NEVER be borrowed onto a case
# that has a real fault, or the evidence contradicts the label.
RESOLVED = re.compile(
    r"value given|credit posted|funds now visible|confirmed settled|"
    r"nothing outstanding|no exception|txn settled|value delivered|"
    r"credit confirmed|no action required|no discrepancy|all clean", re.I)

# Lines describing money moving onward fast to new accounts. For a fraud case
# with no structured onward-transfer list, one of these IS the evidence.
MOVEMENT = re.compile(
    r"onward|fan[- ]out|emptied|moved the funds on|moved on|tranche|"
    r"opened this week|days old|no other activity|drained|split", re.I)

# Lines that say nothing about the fault, so they are safe to move between
# cases without changing what the correct answer is.
CHATTER = re.compile(
    r"voicemail|line dropped|no answer|called again|call back|callback|"
    r"switched off|hung up|awaiting|pending|no update|followed up|"
    r"nothing new|reassigned|no response|apologis|calmed|irate|"
    r"escalated to team lead|advised cust|sent reminder|chasing", re.I)


# NO_BREAK covers four unrelated situations. A trace written for one of them
# is simply wrong on the other three, so each trace is tagged and matched to
# the case's actual sub-cause rather than drawn at random.
SUBCAUSE = {
    "fee":     re.compile(r"\bfee|charge|VAT|tariff|commission|net of\b", re.I),
    "name":    re.compile(r"\bspell|name[- ]match|name enquiry|variant|surname|"
                          r"transpos|initial|same person\b", re.I),
    "two":     re.compile(r"\btwo (genuine|separate|distinct|real)|second instruction|"
                          r"separate references|not a duplicate|two payments|"
                          r"distinct reference|both debits\b", re.I),
    "late":    re.compile(r"\blate|delay|cut[- ]off|posting cycle|next[- ]day|"
                          r"queued|after the reconciliation\b", re.I),
}


def subcause_of(case):
    """Which flavour of 'nothing is wrong' is this case?"""
    if case.get("name_enquiry"):
        return "name"
    led = case.get("ledger", [])
    if any("CHG" in (l.get("narration") or "") for l in led):
        return "fee"
    amt = case["amount_ngn"]
    if sum(1 for l in led if l["dr_cr"] == "DR"
           and abs(l["amount_ngn"] - amt) < 0.01) >= 2:
        return "two"
    return "late"


def tag_trace(t):
    for name, rx in SUBCAUSE.items():
        if rx.search(t):
            return name
    return None


def _clean(rows):
    return [s for s in rows if s and not PIDGIN.search(s)]


class Pools:
    def __init__(self):
        self.inp, self.out = {}, {}
        if not os.path.isdir(TEXT):
            return
        for fn in os.listdir(TEXT):
            if not fn.endswith(".json"):
                continue
            kind, side, _ = fn.split(".")
            d = json.load(open(os.path.join(TEXT, fn)))
            if side == "in":
                self.inp[kind] = {"complaints": _clean(d.get("complaints", [])),
                                  "remarks": _clean(d.get("remarks", []))}
            else:
                self.out[kind] = {"traces": _clean(d.get("traces", [])),
                                  "notes": _clean(d.get("notes", []))}
        # Chatter must be content-free AND must not assert that the case is
        # fine - an earlier version borrowed "funds now visible" onto fraud
        # cases, so the evidence argued against the label.
        self.chatter = [s for v in self.inp.values() for s in v["remarks"]
                        if CHATTER.search(s) and not RESOLVED.search(s)]

    def ready(self):
        return len(self.inp) == 7 and len(self.out) == 7


def fill(s, c, r):
    """Put real values into the {placeholders} the agents used."""
    amt = c["amount_ngn"]
    fee = 10.0 if amt <= 5000 else (25.0 if amt <= 50000 else 50.0)
    # If the case actually lists onward transfers, {n} must be THAT number.
    # Letting it be random taught the model to state counts it could not see.
    onward = c.get("onward_transfers") or []
    # If the fan-out was described in the remarks instead of listed, lift the
    # count out of that text so the trace quotes the same number.
    if not onward:
        m = re.search(r"(\d+)\s+(?:onward transfers|tranches|different banks)",
                      " ".join(c.get("remarks") or []))
        stated = int(m.group(1)) if m else None
    else:
        stated = len(onward)
    vals = {
        "amount": f"{amt:,.2f}",
        "ref": c.get("transaction_ref", "REF" + "0" * 9),
        "bank": c["beneficiary"]["bank"],
        "n": str(stated if stated else r.randint(2, 7)),
        "minutes": str(r.choice([3, 5, 10, 15, 20, 25, 40, 90])),
        "days": str(r.randint(1, 9)),
        "fee": f"{fee:,.2f}",
        "vat": f"{fee * 0.075:,.2f}",
        "shortfall": f"{amt * r.uniform(0.03, 0.4):,.2f}",
    }
    for k, v in vals.items():
        s = s.replace("{" + k + "}", v)
    s = re.sub(r"\{[a-z_]+\}", "", s)
    # Agents wrote "under {days} old" and "within {minutes}", which render as
    # "under 2 old". Put the unit back rather than rewriting 280 lines by hand.
    s = re.sub(r"\b(\d+)\s+old\b", r"\1 days old", s)
    s = re.sub(r"\bwithin (\d+)(?=[ ,.])(?!\s*(?:minute|hour|day|second))",
               r"within \1 minutes", s)
    return re.sub(r"\s{2,}", " ", s).strip()


CROSS_COMPLAINT_RATE = 0.35


def dress(pools, c, kind, r, when):
    """Replace the case's prose with agent-written text."""
    from datetime import timedelta
    src = kind
    if r.random() < CROSS_COMPLAINT_RATE:
        src = r.choice([k for k in pools.inp if k != kind])
    comp = pools.inp[src]["complaints"]
    if comp and r.random() < 0.88:
        c["customer_complaint"] = fill(r.choice(comp), c, r)
    else:
        c["customer_complaint"] = None

    # Two failures were possible here and both happened once.
    #  * Replacing the remarks wholesale deleted the fault's own evidence and
    #    made 47% of fraud cases unanswerable.
    #  * Keeping the fault's TEMPLATE text handed a regex the exact string it
    #    needed - the rules baseline jumped straight back to 96%.
    # So: drop the template, but guarantee at least one SUBSTANTIVE line from
    # this fault's own agent-written pool. Evidence is always present, and it
    # is always in somebody's own words.
    own = pools.inp[kind]["remarks"]
    meaty = [s for s in own if not CHATTER.search(s)] or own
    # A fraud case with no structured onward-transfer list must carry a remark
    # that actually describes the money moving on. Otherwise the answer cites
    # evidence the case does not contain, and the model learns to invent it.
    if kind == "SUSPECTED_FRAUD" and not (c.get("onward_transfers") or []):
        movers = [s for s in own if MOVEMENT.search(s)]
        if movers:
            meaty = movers
    lines = [fill(r.choice(meaty), c, r)] if meaty else []
    for _ in range(r.choices([0, 1], weights=[62, 38])[0]):
        if own:
            lines.append(fill(r.choice(own), c, r))
    for _ in range(r.choices([0, 1, 2], weights=[45, 38, 17])[0]):
        if pools.chatter:
            lines.append(fill(r.choice(pools.chatter), c, r))
    r.shuffle(lines)

    stamped, t = [], when
    for ln in lines:
        t = t + timedelta(hours=r.randint(1, 30))
        stamped.append(f"{t.strftime('%d/%m %H:%M')} "
                       f"{r.choice(['CS', 'OPS', 'CS', 'RECON', 'BRANCH'])}: {ln}")
    c["remarks"] = stamped or None


def analyst(pools, c, kind, r):
    """Pick the analyst's reasoning and closing note for this fault.

    For NO_BREAK the pool covers four different reasons, so the trace and the
    note are both filtered to the one this case actually is. Drawing at random
    produced answers that cited name spellings on a case with no name enquiry.
    """
    d = pools.out.get(kind)
    if not d or not d["traces"]:
        return None, None
    traces, notes = d["traces"], d["notes"]
    if kind == "NO_BREAK":
        want = subcause_of(c)
        tr = [t for t in traces if tag_trace(t) == want]
        nt = [n for n in notes if tag_trace(n) == want]
        traces = tr or traces
        notes = nt or notes
    return fill(r.choice(traces), c, r), fill(r.choice(notes), c, r)
