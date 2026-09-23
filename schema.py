"""What can go wrong with a payment, and what you are supposed to do about it.

Six failure modes plus a false-alarm class, and six actions. Everything else in
this project references these lists, so a name changes here and nowhere else.
"""

BREAKS = {
    "SWITCH_TIMEOUT_NO_REVERSAL":
        "Customer was debited, the switch timed out, the beneficiary bank never "
        "credited, and the automatic refund never fired.",
    "DUPLICATE_POSTING":
        "The same transfer hit the ledger twice. Customer debited twice for one "
        "instruction.",
    "REVERSAL_NOT_APPLIED":
        "A refund was instructed and acknowledged, but never posted to the "
        "customer's account.",
    "WRONG_BENEFICIARY":
        "Money landed in an account that does not match the name on the "
        "instruction.",
    "PARTIAL_SETTLEMENT":
        "The amount in the settlement file does not match the amount on the "
        "ledger.",
    "SUSPECTED_FRAUD":
        "The pattern looks like fraud - rapid fan-out to many new beneficiaries, "
        "or a chain that drains onward within minutes.",
    "NO_BREAK":
        "A false alarm. It looks like an exception but the money settled "
        "correctly. Most of a real queue is this.",
}

ACTIONS = {
    "AUTO_REVERSE":            "Reverse it automatically and tell the customer.",
    "MANUAL_CREDIT":           "Credit the beneficiary by hand; the money did arrive at the other bank.",
    "RECOVER_FROM_BENEFICIARY":"Raise a recall against the receiving bank.",
    "NO_ACTION_SETTLED":       "Nothing wrong. It settled correctly. Close it.",
    "ESCALATE_FRAUD":          "Freeze and send to the fraud desk. Do not close.",
    "ESCALATE_MANUAL":         "Not enough evidence either way. A human must look.",
}

# The action a correct system takes for each break, when the case is clean.
CLEAN_ACTION = {
    "SWITCH_TIMEOUT_NO_REVERSAL": "AUTO_REVERSE",
    "DUPLICATE_POSTING":          "AUTO_REVERSE",
    "REVERSAL_NOT_APPLIED":       "MANUAL_CREDIT",
    "WRONG_BENEFICIARY":          "RECOVER_FROM_BENEFICIARY",
    "PARTIAL_SETTLEMENT":         "ESCALATE_MANUAL",
    "SUSPECTED_FRAUD":            "ESCALATE_FRAUD",
    "NO_BREAK":                   "NO_ACTION_SETTLED",
}

CHANNELS = ["NIP", "USSD", "POS", "WEB", "AGENT"]

# Three-digit institution codes. Real format, illustrative allocation.
BANKS = {
    "035": "Wema Bank", "058": "GTBank", "057": "Zenith Bank",
    "044": "Access Bank", "033": "United Bank for Africa",
    "011": "First Bank", "232": "Sterling Bank", "50211": "Kuda MFB",
    "50515": "Moniepoint MFB", "100004": "OPay",
}

# Switch response codes, ISO-8583 shaped.
RESP = {
    "00": "Approved or completed successfully",
    "09": "Request in progress",
    "91": "Beneficiary bank not available",
    "06": "Invalid transaction",
    "26": "Duplicate transaction",
    "25": "Unable to locate record",
    "13": "Invalid amount",
}
