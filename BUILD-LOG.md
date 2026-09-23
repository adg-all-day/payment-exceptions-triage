# Payments exceptions model — build log

Running record of what was built, what broke, and every number measured.
Kept because the evaluation evidence *is* the product, and because a judge or a
bank's model-risk function will ask how the thing was made.

**Project:** deagatech.com — first product.
**Target:** a working prototype for a Nigerian bank's payment operations team.
**What it does:** reads a payments exception (a transfer that did not settle
cleanly), says what went wrong, traces where the money went, recommends an
action, drafts the note, and reports how sure it is.
**Why a small model:** the data is customer transaction records. It cannot leave
the bank. So the model has to run on their hardware, and they have to own it.

---

## 0. Ground rules set before any code

| Decision | Reason |
|---|---|
| Synthetic data only | No bank has given us data. Everything here is invented. Nothing touches a real institution. |
| Code decides the ANSWER | If code causes the fault, the correct label is certain. No annotation, no disagreement. |
| A model writes the PROSE | Templated text is regex-solvable; see §3, where this nearly sank the project. |
| Eval harness built BEFORE the model | It is the deliverable being sold. It cannot be the thing rushed at the end. |
| Test set never gets label noise | The test set is the ruler. A bent ruler measures nothing. |
| Fraud is the headline metric | Ten thousand correctly closed false alarms earn nothing. One missed fraud ends the contract. |

---

## 1. The domain model

Seven classes. Six real faults plus a false-alarm class, because most of a real
exception queue turns out to be nothing.

| Class | Meaning | Correct action |
|---|---|---|
| `SWITCH_TIMEOUT_NO_REVERSAL` | Debited, switch never confirmed, no credit, auto-refund never fired | Reverse automatically |
| `DUPLICATE_POSTING` | One instruction hit the ledger twice | Reverse the extra leg |
| `REVERSAL_NOT_APPLIED` | Refund raised and acknowledged but never posted | Credit the customer by hand |
| `WRONG_BENEFICIARY` | Credited to a genuinely different person | Recall from the receiving bank |
| `PARTIAL_SETTLEMENT` | Ledger and settlement file disagree, and it is not a fee | Refer to settlement ops |
| `SUSPECTED_FRAUD` | Credited then fanned out to new accounts; customer denies it | Freeze, escalate, never close |
| `NO_BREAK` | False alarm; it settled correctly | Close, no action |

Each case carries what a Nigerian back office would actually read: ledger legs,
an ISO-8583-shaped switch response, a settlement file line, a NIP session id, a
NUBAN account number, a customer complaint, and a free-text remarks log.

---

## 2. The traps, and why each one is there

Difficulty was designed in, not hoped for.

- **Fee vs shortfall.** Some amount mismatches are exactly the transfer charge
  plus 7.5% VAT. That is `NO_BREAK`, not `PARTIAL_SETTLEMENT`. A rules engine
  comparing two numbers gets this wrong.
- **Name variants.** "C. Okafor", "Okafor Chioma" and "CHIOMA OKAFOR" are one
  person. "Musa Bello" is not. Requires reading, not string comparison.
- **Two real transfers vs one duplicate.** Same amount, same day, same
  beneficiary — but different references. Not a duplicate.
- **Ambiguity (8.6% of cases).** Deciding evidence deliberately removed. The only
  correct answer is `ESCALATE_MANUAL`. Never applied to fraud — a manufactured
  "acceptable miss" on fraud would poison the training set.
- **Overlap (10%).** Two faults on one case; the graver one is the answer.
- **Label noise (3%, TRAIN ONLY).** Real analysts working a queue get some wrong.

---

## 3. The failure that changed the design

**First attempt: generate everything with code, including the prose.**

Result: the if-then rules baseline scored **96.6%**. Which means the demo would
have proved nothing — a judge asks "why not just write rules?" and the honest
answer is "no reason".

Root cause, and it is not fixable by adding more surface mess: **if code
generates the data, code can un-generate it.** The generator's logic is
recoverable by an engineer with regexes.

**Second attempt: same code-generated records, but agent-written free text.**

Rules baseline fell to **85.5%**, and — the important part — fraud detection
collapsed. The giveaway now reads *"beneficiary account emptied within 20
minutes across 5 onward transfers, all to accounts opened this week"*, which is
ordinary English, not a field. You can chase that with more regexes forever.
**The whack-a-mole is the argument.**

---

## 4. How the text was written

14 agents, run in parallel, all on Claude:

- **7 agents on the input side** — 50 customer complaints and 50 internal log
  lines per class. Instructed never to name the fault (customers describe
  symptoms), to vary register hard, and deliberately to write phrasings that
  could belong to a different fault.
- **7 agents on the analyst side** — 40 reasoning traces and 40 closing notes
  per class, told to reason from evidence to conclusion rather than assert.

Yield: **350 complaints, 350 log lines, 280 traces, 280 notes.**

Two safeguards applied when mixing this into cases:

1. **Cross-mixing (35%).** The complaint is drawn from a *different* class's
   pool a third of the time, so the model cannot learn the pool instead of the
   evidence.
2. **Safe distractors only.** Remarks often carry the deciding fact, so they are
   not mixed freely — a fraud remark on a timeout case would change the correct
   answer. Only content-free chatter ("left voicemail", "line dropped") crosses
   pools.

A Pidgin filter strips lines that slipped through despite the instruction.

---

## 5. Data as built

```
train 4000   test 1000     seed 20260825    fingerprint 5ebe0cba593b
  NO_BREAK                        1185   23.7%
  SWITCH_TIMEOUT_NO_REVERSAL      1095   21.9%
  DUPLICATE_POSTING                683   13.7%
  REVERSAL_NOT_APPLIED             665   13.3%
  WRONG_BENEFICIARY                555   11.1%
  PARTIAL_SETTLEMENT               436    8.7%
  SUSPECTED_FRAUD                  381    7.6%
  (ambiguous, must defer)          428    8.6%
  (train labels deliberately wrong) 119
```

---

## 6. The scorer

Reports break-type accuracy, action accuracy, per-class accuracy, a confusion
matrix, deferral behaviour, confidence calibration, and:

**the fraud miss rate, split into "called it something else" and
"called it something else AND was willing to close it without a human".**
The second number must be zero.

**Validated before use** against two fake models:

| Fake model | Break-type accuracy | Fraud missed |
|---|---|---|
| Oracle (returns the gold answer wrapped in prose + a code fence) | 100.0% | 0% |
| Lazy (always says "nothing wrong") | 20.1% | 100% |

That confirms the forgiving JSON parser and the marking logic both work.

---

## 7. Baseline to beat

A deliberately **competent** rules engine — parses the settlement line, hunts
reversal references, keyword-matches the remarks, normalises names before
comparing. Roughly what a good engineer produces in a day or two. Not crippled.

```
break type correct     85.5%
action correct         80.5%

fraud cases in test    58
missed                 30  (51.7%)
MISSED AND AUTO-CLOSED 28  (48.3%)   <-- must be 0

SWITCH_TIMEOUT_NO_REVERSAL   197/205   96.1%
DUPLICATE_POSTING            144/155   92.9%
REVERSAL_NOT_APPLIED          65/140   46.4%
WRONG_BENEFICIARY             91/103   88.3%
PARTIAL_SETTLEMENT            84/92    91.3%
```

**Read this the way a bank would:** 85.5% looks respectable, and the thing would
quietly auto-close half the fraud that crossed it.

---

## 8. Infrastructure, and everything that broke

Training runs on Google Cloud so it never touches the demo laptop.

| Problem | Diagnosis | Fix |
|---|---|---|
| `g2-standard-32` unavailable in us-central1-a | Genuine stockout | Try many zones, spot then on-demand |
| Every zone failed | **`GPUS_ALL_REGIONS` quota was 0** — no GPU could start anywhere | Filed a quota increase via the Cloud Quotas API; granted |
| SSH `Permission denied (publickey)` | Project metadata held a stale key from June | Pushed the current key to instance metadata |
| Still denied | Key was `ssh-rsa`; modern macOS OpenSSH refuses SHA-1 RSA | Generated an ed25519 key |
| `scp` and even `cat file` blocked locally | Sandbox denied reads inside the newly-created project dir | Rebuilt the project in a sibling directory; regenerated data from the same seed |
| `torchaudio` import crash on the VM image | Version mismatch after upgrading transformers | Removed torchaudio; unused here |
| `SFTConfig() got an unexpected keyword 'warmup_ratio'` | trl 1.10 renamed it | `warmup_steps=15` |
| `Target module Gemma4ClippableLinear is not supported` | Gemma 4 E2B wraps the **vision tower's** linears in a custom class LoRA cannot attach to | Target the text decoder layers by regex — 205 layers, and the vision tower is not wanted anyway for a text task |
| `apply_chat_template requires jinja2>=3.1.0` | Image shipped 3.0.3 | Upgraded to 3.1.6 |

Final rig: **1x NVIDIA L4 (23 GB), g2-standard-32 (32 vCPU, 125 GB RAM),
us-east1-c, spot.**

---

## 9. Training run

```
model    google/gemma-4-E2B-it
method   LoRA  r=32  alpha=64  dropout=0.05
targets  205 text-decoder linears (q,k,v,o,gate,up,down)
data     4000 examples, loss on the ANSWER only
epochs   2      effective batch 16 (bs 1 x accum 16)
lr       1e-4 cosine, 15 warmup steps
steps    500    ~20 s/step    ~2 h 45 m
```

**Status: running.**

---

## 10. What still has to be measured

Four models, same 1000 held-out cases, all offline:

1. Rules engine — **done, 85.5%**
2. Gemma 4 E2B, untrained — the "before" picture
3. Gemma 4 26B, untrained — the big-model comparison
4. Gemma 4 E2B, fine-tuned — the product

The result to aim at: **the small model trained on their data beats the
big model that was not — on one laptop, with the wifi off.**

Not yet proven. It goes in this file either way.

---

## 11. Eval path validated mid-training (26 Aug)

Batched inference added before the eval passes: left-padded (decoder-only models
need padding on the left or the pad tokens sit between prompt and answer),
longest-prompt-first so batches hold similar lengths and waste less compute.

Smoke-tested on CPU while the GPU trained, 4 cases through the **untrained**
E2B model. It parses cleanly and emits valid enum values, so the output format
is not the difficulty. The judgement is:

| Gold | Untrained model said | Confidence |
|---|---|---|
| `SWITCH_TIMEOUT_NO_REVERSAL` / auto-reverse | right class, **wrong action** (manual credit) | 0.85 |
| `SUSPECTED_FRAUD` / escalate | **`NO_BREAK`, close it** | **0.95** |
| ambiguous, should defer | `AUTO_REVERSE`, no deferral | **1.00** |
| `WRONG_BENEFICIARY` | `PARTIAL_SETTLEMENT` | 0.95 |

**The untrained model is confidently wrong and never asks for a human.** It
auto-closed a fraud at 0.95 confidence and answered an unanswerable case at 1.00.

That is a stronger "before" picture than a plain accuracy gap, and it is the
argument for why the eval harness — not the model — is the thing being sold.

**Known gap:** loss values are not visible in the log. `nohup` block-buffers
stdout, so the loss dicts are sitting in a buffer while tqdm (stderr, unbuffered)
shows progress. Training is confirmed healthy by GPU utilisation at 99% and a
steady 19.4 s/step. Use `python3 -u` next time.

---

## 12. First training run, and the bug it exposed (26 Aug)

Trained 2 epochs, 500 steps, 2 h 41 m. Final loss **0.4204** (last step 0.2302),
token accuracy **91.4%**.

**Results on the first dataset:**

| | Rules | Untrained E2B | Fine-tuned E2B |
|---|---|---|---|
| Break type correct | 85.5% | **46.3%** | **89.9%** |
| Action correct | 80.5% | 34.8% | 83.1% |
| Fraud missed | 51.7% | **100%** | 39.7% |
| Fraud missed AND auto-closed | 48.3% | 63.8% | 37.9% |
| Unreadable answers | 0% | 2.9% | **0%** |

Fine-tuning roughly **doubled** accuracy over the same model untrained. The two
classes that improved most were the two that require reading prose rather than
matching fields:

- `REVERSAL_NOT_APPLIED` **6.4% -> 80.0%** (the refund reference is in the remarks log)
- `WRONG_BENEFICIARY` **10.7% -> 100%** (is this the same person, spelled differently?)

**But fraud recall was only 60%, and 38% of fraud would still have been
auto-closed.** Investigating that rather than shipping it found a real bug.

### The bug

`textpool.dress()` replaced `case["remarks"]` wholesale with agent-written text.
The fault functions had already written the fan-out evidence into that same
list. For the 55% of fraud cases with no structured `onward_transfers` array,
**that deleted the only evidence there was.**

Measured: **47% of fraud cases in the test set contained no detectable signal at
all.** They were unanswerable. The model was being marked wrong on cases no
analyst could have called either.

### The fix, which took two attempts

**Attempt 1 - keep the generator's remarks.** Rules baseline jumped to **96.2%**
with **0% fraud missed**. Worse than the bug: the generator writes template
text, and the rules regex matches templates perfectly. Straight back to the
original §3 problem.

**Attempt 2 - guarantee one SUBSTANTIVE agent-written remark per case.** Drop
the template entirely; always draw at least one line from this fault's own pool
that is not chatter. Evidence is always present, and always in somebody's own
words.

| | Before fix | Attempt 1 | Attempt 2 |
|---|---|---|---|
| Fraud cases with no signal | 47% | 0% | **0%** |
| Rules baseline accuracy | 85.5% | 96.2% (broken) | **85.5%** |

**The lesson:** evidence has to be present *and* expressed
in natural language. Present-but-templated is a regex exercise. Natural-but-
absent is unanswerable. Only both together describe the real job.

The 26B evaluation was killed 70 cases in - its results would have been
invalidated by the regenerated data. Retraining from scratch on the corrected
set (fingerprint `cae59f44b6de`).

---

## 13. The safety gate

The model alone will not get fraud auto-closure to zero, and it should not have
to. A bank does not accept "the model is usually right" on the one error that
ends the relationship. The dangerous action is made **impossible**, not unlikely.

`gate.py` sits after the model. If any fraud signal is present - money moving
onward fast, receiving accounts days old, or the customer denying they
authorised it - the system may not close the case, whatever the model decided.
It only ever escalates; it never downgrades. Unparseable model output is also
routed to a human rather than dropped.

Measured on the corrected test set:

| | |
|---|---|
| Fraud cases the gate catches | **62%** |
| Non-fraud it also holds (the cost) | **4%** |

That trade is deliberate. Some ordinary cases go to a human because the customer
wrote "I did not authorise this". A wasted review costs minutes; a missed fraud
costs the relationship.

**This is a system property, not a model property** - and it is the part a bank's
model-risk function will actually ask about.

---

## 14. Second training run

Same recipe, corrected data. **Running.**

Note: the restart initially crashed with
`AttributeError: 'functools.partial' object has no attribute '__func__'` inside
trl's chunked cross-entropy patch. Cause: ollama was still holding 15 GB of the
24 GB GPU from the killed 26B run, so `device_map="auto"` offloaded part of the
model to CPU, and accelerate's hook wrapped `forward` in a `functools.partial`
that trl could not introspect. Freeing the GPU fixed it. Worth remembering: that
error means "not enough VRAM", not "bad trl version".

---

## 15. Third run — the training data was teaching the model to lie

Tom asked a plain question — *what do the training prompts actually look like?* —
and printing one answered it badly. This fraud example had:

- `onward_transfers: []` — empty
- remarks reading *"value given at benef end"* and *"funds now visible"*
- a target answer asserting *"the 5 onward hops within 25 minutes"*

**The answer cited evidence the case did not contain, and the remarks argued
against the label.** Measured across the training set:

| | |
|---|---|
| Fraud cases whose answer cites absent evidence | **42%** |
| Faulty cases carrying a "it settled fine" remark | 2% |

A model trained on that learns to state fan-out details it cannot see. For a
bank, a model that fabricates evidence is worse than one that is merely wrong —
it is unauditable.

**Cause.** `textpool.analyst()` drew the reasoning trace at random from the
class pool, independently of what the case actually held. `fill()` then
substituted a *random* number for `{n}`. And cross-pool chatter could import a
line asserting the case was resolved.

**Three fixes:**

1. A fraud case with no structured onward-transfer list must carry a remark that
   genuinely describes money moving onward — drawn from the subset of its own
   pool that says so.
2. `{n}` binds to `len(onward_transfers)` when the list exists, instead of a
   random integer.
3. Chatter borrowed across pools is filtered to exclude anything asserting the
   case settled correctly.

| | Before | After |
|---|---|---|
| Fraud answers citing absent evidence | 42% | **0%** |
| Faulty cases with contradicting remark | 2% | **1%** |

Rules baseline on the corrected data: **84.7%**, fraud missed **31.5%**. Lower
fraud-miss than before because the evidence is now reliably present — a harder
baseline to beat, which is the honest starting point.

Second training run killed at step 401/500 (~2 h in). Retraining on data
fingerprint `44dc9843d392`.

**The pattern across all three runs is worth stating.** Every defect so far was
found by *looking at the data*, not by looking at the metrics — the metrics
looked plausible each time. That is the argument for the eval harness being the
product: it is the thing that makes looking systematic.

---

## 16. Third training run — the results that count

Data fingerprint `44dc9843d392`. 500 steps, 2 h 42 m, final training loss
**0.426** (last logged step 0.2577), on one NVIDIA L4.

Scored on the 1,000 held-out cases the model has never seen.

| | Rules engine | Untrained E2B | **Fine-tuned E2B** | **+ safety gate** |
|---|---|---|---|---|
| Break type correct | 84.7% | 49.1% | **93.7%** | **93.7%** |
| Action correct | 80.5% | 32.6% | 84.6% | 83.3% |
| Fraud missed | 31.5% | 98.6% | **1.4%** | **1.4%** |
| **Fraud missed AND auto-closed** | 48.3% | 68.5% | 1.4% | **0.0%** |
| Unreadable answers | 0% | 5.7% | 0.5% | **0%** |

### What the numbers say

**The untrained model auto-closed 50 of 73 frauds.** Not "got them wrong" —
closed them, confidently, with no human review. That is the honest before
picture, and it is more persuasive than any accuracy figure.

**Fine-tuning nearly doubled accuracy on the same model**, 49.1% to 93.7%. The
weights are identical; only the training on this bank's own history differs.

**The two biggest per-class gains are both prose-reading tasks:**

| Class | Untrained | Fine-tuned | Why it is hard |
|---|---|---|---|
| `REVERSAL_NOT_APPLIED` | 9.2% | **73.1%** | the refund reference is buried in a remarks log |
| `WRONG_BENEFICIARY` | 18.2% | **100%** | is "C. Okafor" the same person as "Chioma Okafor"? |

Those two are the argument for a language model over rules, stated in numbers.

**The safety gate does the last mile.** The model still misclassifies one fraud
case out of 73. The gate refuses to close it anyway, so a human sees it. That is
the distinction worth being precise about with a bank: *the model may be wrong;
the system may not be dangerous.*

Its cost is measured, not assumed — it holds 8.2% of all cases for review, and
action accuracy drops 84.6% -> 83.3% because escalating counts as wrong when the
gold answer was to close. A wasted review costs minutes. A missed fraud costs the
relationship.

### Still weak

`REVERSAL_NOT_APPLIED` at 73.1% is the worst class and the obvious next target.

### Not yet measured

The 26B comparison failed on the first attempt with HTTP 404 — the model had been
pulled while ollama ran as a system service, then the evaluation started a second
server under a different user with an empty model store. Re-running against the
service. ~2 h.

---

## 17. Two design flaws found by reading the data, not the metrics

**a. The reasoning comes after the answer.** The JSON puts `break_type` first and
`money_trace` second. Models generate left to right, so it commits to a verdict
and *then* writes the justification. That is post-hoc rationalisation, not
reasoning — chain-of-thought only helps when the thinking precedes the
conclusion. Reordering the fields is a one-line change and is the cheapest
remaining gain.

**b. This is not reasoning distillation, despite looking like it.** The traces
were written by agents as generic per-class templates and then filled with each
case's values. They were *selected*, not *derived*. Printing three examples made
the consequences visible:

| Defect | What it looked like |
|---|---|
| Wrong sub-cause | Case was two genuine transfers; the trace argued about name spellings, on a case with no name enquiry at all |
| Wrong number | Remarks said "7 tranches"; the trace said "6 onward transfers" |
| Broken unit | "destination accounts under 2 old" — the placeholder lost its noun |
| Severed fragment | "Sequence matters here." then straight to the caveat |

Fixed: NO_BREAK traces are now tagged by sub-cause and matched to the case
(**100%** match, from random); `{n}` binds to the real count, lifted from the
remark text when there is no structured list; units are repaired; the ambiguous
path no longer truncates the trace. Verified on data `4ba6c7ab39dd`.

**None of this moved the labels** — classification was already correct, which is
why 93.7% stands. It moved the *audit trail*, which for a bank is the deliverable.

---

## 18. Architecture question settled: retrieval, not agency

Should the model be handed the case, or given read-only API access and left to
fetch what it needs?

**Decision: a deterministic retriever assembles the case pack; the model judges.**

Against agentic tool use *for this product*:

- Reliable tool selection scales with model size. A 2B model will pick wrong
  tools and loop.
- "Your model calls our core banking APIs" is a far harder security review than
  "we send it a file".
- Model risk requires reproducibility. Different lookups on re-run means the
  evidence pack is not reproducible — and the evidence pack is what is being sold.
- Training agentic behaviour needs a simulator to act in. That is a separate build.

**But the lookups are written as named tools from day one** — `get_account_age`,
`get_onward_transfers`, `get_prior_disputes`. Today code calls them in a fixed
order. Going agentic later changes *who* calls them, not *what* they are. The
option costs nothing to keep open.

Agentic is right for the **second** product: an investigation assistant a human
drives, where the needed lookups cannot be known in advance and non-determinism
is acceptable because a person is in the loop.

---

## 19. Final results — all five systems, same 1,000 unseen cases

```
  SYSTEM                           break   action    fraud    AUTO-   unread
                                    type            missed   CLOSED     able
  1  rules engine, no AI           84.7%    80.5%    31.5%    30.1%     0.0%
  2  Gemma 4 E2B, untrained        49.1%    32.6%    98.6%    68.5%     5.7%
  3  Gemma 4 26B, untrained        69.5%    51.9%    30.1%    15.1%     0.0%
  4  Gemma 4 E2B, FINE-TUNED       93.7%    84.6%     1.4%     1.4%     0.5%
  5  fine-tuned + safety gate      93.7%    83.3%     1.4%     0.0%     0.0%
```

### The three findings worth saying out loud

**1. Small and taught beats big and generic, decisively.** The fine-tuned 2B
model beats the untrained 26B on every column: 93.7% against 69.5%, and fraud
auto-closure 0% against 15.1%. Thirteen times the parameters and it loses.

**2. Big and generic also loses to a day of engineering.** The 26B scores 69.5%
against the rules engine's 84.7%. The ordering is
**big generic AI < plain if-then rules < small model taught on your own data**,
which is counter-intuitive enough to be memorable and is the real argument
against renting a frontier API for this job.

**3. The one class that decides it.** `REVERSAL_NOT_APPLIED` — where the refund
reference is a sentence in a remarks log:

| System | Score |
|---|---|
| rules engine | 46.4% |
| Gemma 4 26B, untrained | 13.4% |
| Gemma 4 E2B, untrained | 9.2% |
| **Gemma 4 E2B, fine-tuned** | **73.1%** |

You have to read it, and you have to have seen how *this* bank writes it.

### A fairness note that must travel with these numbers

The 26B was run with **thinking mode disabled**. Left enabled it spends its
entire token budget reasoning and returns an empty response — the first attempt
scored 0.0% with 100% unreadable for exactly that reason, which was a harness
fault, not a model fault. With thinking off it answers directly in 3.6 s/case and
produces clean JSON on every case (0% unreadable). Anyone quoting the 69.5%
should quote this alongside it.

### Cost and time

| | |
|---|---|
| Training | 2 h 42 m, one NVIDIA L4 spot instance |
| Four evaluation passes | ~1 h 40 m |
| Total GPU spend | roughly $3 |
| Wall clock including three restarts | about 14 hours |

### Artefacts kept

- `artifacts/out/lora/` — the adapter, 185 MB, plus checkpoints
- `artifacts/out/preds_*.jsonl` — every prediction from every system, gated and
  ungated, so any number here can be recomputed
- `final_table.py` — regenerates the scoreboard from those files
- `training-examples.html` — seven training rows verbatim
- `training-erd.pdf` — the technical entity/flow diagram
- `how-the-model-is-made.pdf` — the plain-English version

GPU instance deleted; nothing is still charging.

### What is NOT done

- **The demo screen was never written.** An earlier entry in this log said
  `app/serve.py` "is written but has not been run" - that was wrong; `app/` is
  empty. Nothing exists to demo with, and the adapter has not been converted for
  Apple silicon either.
- The adapter has not been converted to 4-bit MLX for the Mac.
- `REVERSAL_NOT_APPLIED` at 73.1% is the weakest class and the obvious next target.
- The reasoning still comes *after* the answer in the JSON. Reordering it is the
  cheapest remaining accuracy gain and has not been tried.
- The traces are selected from a pool, not derived per case. True reasoning
  distillation remains the biggest quality upgrade available.
