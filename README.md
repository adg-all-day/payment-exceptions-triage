# Payment exceptions triage — a small model that beats a big one

A 2-billion-parameter language model, fine-tuned on a Nigerian bank's own
exception history, that reads a failed payment and works out what happened to
the money.

It runs on the bank's own hardware. No payment record ever leaves the building.

## The result

Five systems, the same 1,000 held-out cases, none of them seen during training.

| System | break type | action | fraud missed | **fraud auto-closed** | unreadable |
|---|---|---|---|---|---|
| Rules engine, no AI | 84.7% | 80.5% | 31.5% | 30.1% | 0.0% |
| Gemma 4 E2B, untrained | 49.1% | 32.6% | 98.6% | 68.5% | 5.7% |
| Gemma 4 26B, untrained | 69.5% | 51.9% | 30.1% | 15.1% | 0.0% |
| **Gemma 4 E2B, fine-tuned** | **93.7%** | **84.6%** | **1.4%** | 1.4% | 0.5% |
| **Fine-tuned + safety gate** | **93.7%** | 83.3% | **1.4%** | **0.0%** | **0.0%** |

Lower is better in the last three columns.

**Fraud auto-closed** means the system called a fraud something else *and* was
willing to close the case with no human ever seeing it. That is the number that
has to be zero, and only the last row gets there.

### Three things these numbers say

**The 2B model you own beats the 26B you would rent.** 93.7% against 69.5%,
on every column. Thirteen times the parameters, and it loses.

**The big generic model also loses to a day of engineering.** 69.5% against the
rules engine's 84.7%. The ordering is *big generic AI < plain if-then rules <
a small model taught on your own data.*

**One class decides it.** `REVERSAL_NOT_APPLIED` — where a refund was raised and
acknowledged, but the money never reached the customer. The case carries the
reversal reference and `acknowledged: true`; what it does not carry is any credit
leg on the account. The evidence is an *absence*, so a rule checking
`acknowledged == true` closes it as settled:

| System | score |
|---|---|
| Gemma 4 E2B, untrained | 9.2% |
| Gemma 4 26B, untrained | 13.4% |
| rules engine | 46.4% |
| **Gemma 4 E2B, fine-tuned** | **73.1%** |

Noticing what is missing is the hard part, and it is why the gap between a rules
engine and a trained model is widest here.

## The safety gate

The model still gets one fraud case in 73 wrong. A bank will not accept "usually
right" on the mistake that ends a customer relationship.

So a hard rule sits after the model. If there is any fraud signal — money moving
straight out again, receiving accounts days old, a customer saying *this was not
me* — the case cannot be closed, whatever the model decided. **It can only
escalate. It can never close.**

Its cost is measured, not assumed: it holds 8.2% of all cases for human review
and gives up 1.3 points of action accuracy. A wasted review costs minutes. A
missed fraud costs the relationship.

*The model may be wrong. The system may not be dangerous.*

## The data is invented, and that is the point

No real bank, customer, or transaction appears anywhere in this repository.

Building it needed two halves that do not work alone:

**Code invents the fault.** A generator creates the ledger entries, the switch
response, the settlement file line. Because it causes the fault, the correct
answer is certain — no labelling, no disagreement, no ambiguity about ground
truth.

**Language models write the human parts.** Fourteen agents wrote the customer
complaints and the remarks analysts type while chasing a case — 350 complaints,
350 remark lines, 280 explanations.

Neither half is optional. When code wrote the human text as templates, a plain
rules engine scored **96.6%** by pattern-matching, and the whole exercise proved
nothing. When the text was written but the evidence deleted, **47%** of fraud
cases became unanswerable and the model was being marked wrong on cases nobody
could have called.

Traps are planted deliberately: amounts that look short but are just the transfer
fee, double charges that are two genuine payments, names that are one person
spelled two ways. In about one case in ten (102 of 1,000 test cases) the evidence is
removed entirely, and the only correct answer is *escalate to a human*.

## What went wrong, three times

`BUILD-LOG.md` is the full record, including the failures. Three times the
dataset was thrown away and rebuilt:

| Defect | How it showed up | Fix |
|---|---|---|
| Evidence too tidy | Rules engine scored 96.6% without understanding anything | Let agents write the human text |
| Evidence deleted | 47% of fraud cases unanswerable — model marked wrong on impossible cases | Guarantee one real clue per case |
| Answers cited evidence that was not there | 42% of fraud explanations named onward transfers the case did not contain | Bind every number to the case's real values |

Every one was found by reading the data. None was visible in the metrics — the
metrics looked fine each time.

## Reproducing it

```bash
python3 gen_cases.py                  # build 5,000 cases, 4,000 train / 1,000 test
python3 baseline_rules.py             # the no-AI baseline to beat
python3 train_lora.py                 # LoRA fine-tune, ~2h40m on one NVIDIA L4
python3 run_model.py --adapter out/lora --out out/preds_tuned.jsonl
python3 gate.py out/preds_tuned.jsonl out/preds_tuned_gated.jsonl
python3 final_table.py                # the scoreboard above
```

Every prediction from every system is committed under `artifacts/out/`.

**One caveat you should know before checking the numbers.** The dataset in
`data/` was regenerated after the evaluation ran, to fix defects in how the
written explanations were matched to each case. Regeneration produces different
cases under different ids, so `data/` and `artifacts/out/preds_*.jsonl` no longer
line up — only about 295 of 1,000 ids are common, and even those may differ in
content. The scores in the table above are real and were computed against the
dataset as it stood at evaluation time; they cannot be recomputed from this
checkout without re-running the models against the current data. That re-run is
the next thing on the list.

| File | What it is |
|---|---|
| `gen_cases.py` | the case generator and the faults it plants |
| `textpool.py` | matches agent-written prose to the case's actual evidence |
| `schema.py` | the seven break types and six actions |
| `baseline_rules.py` | the rules engine, written before the model |
| `train_lora.py` | the fine-tune |
| `score.py` / `final_table.py` | the scoring harness |
| `gate.py` | the safety gate |
| `BUILD-LOG.md` | what was built, what broke, and why |

## Cost

| | |
|---|---|
| Training | 2 h 42 m on one NVIDIA L4 spot instance |
| Four evaluation passes | ~1 h 40 m |
| Total GPU spend | roughly $3 |
| Adapter | 185 MB — runs on a laptop at ~2.5 GB packed |

## Honest limitations

- **The offline laptop demo does not exist yet.** The adapter has not been
  converted for Apple silicon and no serving script is written. The numbers here
  are all from the evaluation harness on a rented GPU.
- **The 26B was run with thinking mode disabled.** Left on it spends its entire
  token budget reasoning and returns nothing — the first attempt scored 0.0%,
  which was this harness failing, not the model. Anyone quoting 69.5% should
  quote this alongside it.
- **The reasoning is generated after the answer.** The output puts the verdict
  first and the explanation second, so the model decides and then justifies.
  Reordering those two fields is the cheapest remaining accuracy gain, untried.
- **Explanations are selected, not derived.** Each is chosen from a pool written
  per break type, then bound to the case's real values. Genuine per-case
  reasoning distillation is the largest quality upgrade still available.
- **`REVERSAL_NOT_APPLIED` at 73.1%** is the weakest class and the obvious next
  target.
- **Tested only on synthetic data.** The measurement that matters — training on
  one time period and testing on a later one, to see whether it survives drift —
  needs real historical exceptions and has not been done.

## Licence

MIT.

## Pitch deck

[`docs/trace-pitch-deck.pdf`](docs/trace-pitch-deck.pdf) — the 10-slide version, with the
industry figures sourced on each slide.
