"""Entity-relationship / flow diagram of the whole training pipeline."""
import sys
sys.path.insert(0, "/Users/adg/Documents/LLM/gemma-lora-lab")
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(15), Inches(8.5)
W, H, M = 15.0, 8.5, 0.55
FONT, MONO = "Helvetica Neue", "Menlo"

INK   = RGBColor(0x16, 0x20, 0x1C)
BODY  = RGBColor(0x33, 0x42, 0x3B)
MUTED = RGBColor(0x6B, 0x7C, 0x74)
LINE  = RGBColor(0xC9, 0xD3, 0xCD)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
PAPER = RGBColor(0xF7, 0xF8, 0xF7)
GREEN = RGBColor(0x0E, 0x6B, 0x4F)   # data / source of truth
BLUE  = RGBColor(0x1E, 0x4E, 0x8C)   # model artefacts
AMBER = RGBColor(0x8A, 0x6A, 0x12)   # agent-written text
RED   = RGBColor(0xB3, 0x34, 0x1F)   # measurement / risk
PURPLE= RGBColor(0x5B, 0x3A, 0x8C)   # delivery


def slide(title, sub):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(W), Inches(H))
    bg.fill.solid(); bg.fill.fore_color.rgb = PAPER
    bg.line.fill.background(); bg.shadow.inherit = False
    tx(s, title, M, 0.32, 12, 0.45, 22, INK, True)
    tx(s, sub, M, 0.78, 13, 0.3, 12.5, MUTED)
    return s


def tx(s, t, x, y, w, h, size=12, col=BODY, bold=False, align=PP_ALIGN.LEFT,
       font=FONT, line=1.25, anchor=MSO_ANCHOR.TOP, italic=False):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    f = tb.text_frame; f.word_wrap = True; f.vertical_anchor = anchor
    f.margin_left = f.margin_right = f.margin_top = f.margin_bottom = 0
    for i, ln in enumerate(str(t).split("\n")):
        p = f.paragraphs[0] if i == 0 else f.add_paragraph()
        p.text = ln; p.alignment = align; p.line_spacing = line
        p.space_after = Pt(1)
        for r in p.runs:
            r.font.size = Pt(size); r.font.color.rgb = col
            r.font.bold = bold; r.font.name = font; r.font.italic = italic
    return tb


def entity(s, x, y, w, name, kind, attrs, col=GREEN, key=None):
    """An ERD box: title bar, optional key line, then attributes."""
    hh = 0.42 + (0.2 if key else 0) + len(attrs) * 0.185 + 0.14
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                             Inches(w), Inches(hh))
    box.fill.solid(); box.fill.fore_color.rgb = WHITE
    box.line.color.rgb = col; box.line.width = Pt(1.6)
    box.shadow.inherit = False; box.adjustments[0] = 0.04
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x + 0.012), Inches(y + 0.012),
                             Inches(w - 0.024), Inches(0.40))
    bar.fill.solid(); bar.fill.fore_color.rgb = col
    bar.line.fill.background(); bar.shadow.inherit = False
    tx(s, name, x + 0.16, y + 0.09, w - 0.9, 0.26, 11.5, WHITE, True)
    tx(s, kind, x + w - 0.92, y + 0.11, 0.78, 0.22, 8, WHITE, False,
       PP_ALIGN.RIGHT, italic=True)
    yy = y + 0.5
    if key:
        tx(s, key, x + 0.16, yy, w - 0.32, 0.2, 9, col, True, font=MONO)
        ln = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x + 0.14), Inches(yy + 0.185),
                                Inches(w - 0.28), Inches(0.012))
        ln.fill.solid(); ln.fill.fore_color.rgb = LINE
        ln.line.fill.background(); ln.shadow.inherit = False
        yy += 0.28
    for a in attrs:
        tx(s, a, x + 0.16, yy, w - 0.32, 0.19, 9, BODY, font=MONO)
        yy += 0.185
    return (x, y, w, hh)


def to_back(shape):
    """Put a connector behind the boxes so it never cuts through text."""
    el = shape._element
    tree = el.getparent()
    tree.remove(el)
    tree.insert(3, el)          # after nvGrpSpPr, grpSpPr and the background


def link(s, a, b, label="", card="", col=MUTED, bend=None):
    """Straight connector between two entity boxes with a cardinality label."""
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    if bx >= ax + aw - 0.05:                     # b is to the right
        x1, y1 = ax + aw, ay + ah / 2
        x2, y2 = bx, by + bh / 2
    elif ax >= bx + bw - 0.05:                   # b is to the left
        x1, y1 = ax, ay + ah / 2
        x2, y2 = bx + bw, by + bh / 2
    else:                                        # vertical
        if by > ay:
            x1, y1 = ax + aw / 2, ay + ah
            x2, y2 = bx + bw / 2, by
        else:
            x1, y1 = ax + aw / 2, ay
            x2, y2 = bx + bw / 2, by + bh
    c = s.shapes.build_freeform(Inches(x1), Inches(y1))
    mid = bend if bend else ((x1 + x2) / 2, (y1 + y2) / 2)
    c.add_line_segments([(Inches(mid[0]), Inches(mid[1])), (Inches(x2), Inches(y2))])
    sh = c.convert_to_shape()
    sh.line.color.rgb = col; sh.line.width = Pt(1.5)
    sh.fill.background(); sh.shadow.inherit = False
    to_back(sh)
    if label:
        tx(s, label, mid[0] - 0.72, mid[1] - 0.30, 1.45, 0.2, 8.5, col, True,
           PP_ALIGN.CENTER)
    if card:
        tx(s, card, mid[0] - 0.72, mid[1] - 0.12, 1.45, 0.2, 8, MUTED, False,
           PP_ALIGN.CENTER, font=MONO)
    return sh


def note(s, t, x, y, w, col=MUTED):
    tx(s, t, x, y, w, 0.5, 9.5, col, False, line=1.3, italic=True)


def legend(s, y):
    items = [("data / ground truth", GREEN), ("agent-written text", AMBER),
             ("model artefact", BLUE), ("measurement", RED), ("delivery", PURPLE)]
    x = M
    for lab, c in items:
        d = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                               Inches(0.22), Inches(0.14))
        d.fill.solid(); d.fill.fore_color.rgb = c
        d.line.fill.background(); d.shadow.inherit = False
        tx(s, lab, x + 0.3, y - 0.03, 1.9, 0.2, 8.5, MUTED)
        x += 2.35

# ======================= PAGE 1 — MANUFACTURING THE DATA ====================
s = slide("Payments exceptions model — 1. Where the training data comes from",
          "Code decides the ANSWER so the label is certain. Agents write the PROSE so the "
          "evidence cannot be pattern-matched. Neither alone is enough.")

gen = entity(s, M, 1.35, 2.55, "FAULT_GENERATOR", "process",
   ["seed          20260825", "n_total       5000", "mix{7 classes}", "ambiguous_rate 0.12",
    "overlap_rate  0.10", "label_noise   0.03"], GREEN)

agent = entity(s, M, 4.55, 2.55, "TEXT_AGENT", "process x14",
   ["break_type    FK", "side          in | out", "yield_in   50 + 50", "yield_out  40 + 40"], AMBER)

pool = entity(s, 3.55, 4.55, 2.6, "TEXT_POOL", "entity",
   ["complaints[]", "remarks[]", "traces[]", "notes[]", "chatter[]  (shared)"], AMBER,
   key="PK  break_type + side")

case = entity(s, 6.7, 1.35, 3.5, "CASE", "entity",
   ["value_date, channel, amount_ngn", "customer{account, name}",
    "beneficiary{account, bank,", "            name_on_instruction}",
    "ledger[]{dr_cr, amount, narration}", "switch{code, message}",
    "settlement_file_line", "name_enquiry{returned, instructed}",
    "onward_transfers[]{age_days}", "customer_complaint      <- pool",
    "remarks[]               <- pool"], GREEN, key="PK  exception_id")

tgt = entity(s, 10.75, 1.35, 3.7, "TARGET", "entity",
   ["break_type    1 of 7", "money_trace   <- pool.traces",
    "action        1 of 6", "confidence    0..1",
    "needs_human   bool", "analyst_note  <- pool.notes"], GREEN,
   key="PK  exception_id  (FK -> CASE)")

ex = entity(s, 10.75, 4.05, 3.7, "EXAMPLE", "entity",
   ["instruction   fixed preamble", "input         CASE as JSON",
    "target        TARGET as JSON", "loss computed on TARGET only"], GREEN,
   key="PK  exception_id")

split = entity(s, 6.7, 5.55, 3.5, "SPLIT", "entity",
   ["train  4000   label noise 3%", "test   1000   never noised",
    "fingerprint  44dc9843d392"], GREEN, key="PK  split_name")

link(s, gen, case, "produces", "1 : N")
link(s, agent, pool, "writes", "1 : 1")
link(s, pool, case, "dresses", "N : M")
link(s, case, tgt, "described by", "1 : 1")
link(s, tgt, ex, "wrapped as", "1 : 1")
link(s, ex, split, "assigned to", "N : 1")

note(s, "Three rules learned the hard way, each after a measured failure:\n"
        "1. Evidence must be PRESENT — deleting the generator's remarks left 47% of fraud cases unanswerable.\n"
        "2. Evidence must be in NATURAL language — keeping the template put the rules baseline back to 96.2%.\n"
        "3. The answer may only cite evidence the case CONTAINS — 42% of fraud answers named onward hops that were not there.",
     M, 6.75, 6.0, RED)
legend(s, 8.05)

# ================== PAGE 2 — TRAINING, MEASURING, DELIVERING ================
s = slide("Payments exceptions model — 2. Training, measuring, delivering",
          "One held-out set of 1000 cases scores four systems. The fraud auto-close rate is "
          "the number that decides whether any of it is sellable.")

base = entity(s, M, 1.3, 2.7, "BASE_MODEL", "artefact",
   ["repo   google/gemma-4-E2B-it", "params ~2B effective",
    "dtype  bfloat16", "vision tower  UNUSED"], BLUE, key="PK  model_id")

trainer = entity(s, M, 3.55, 2.7, "TRAINER", "process",
   ["trl SFTTrainer", "epochs 2   steps 500", "batch 1 x accum 16",
    "lr 1e-4 cosine, warmup 15", "max_length 3072", "grad checkpointing ON"], BLUE)

lora = entity(s, 3.7, 1.3, 2.75, "LORA_ADAPTER", "artefact",
   ["r 32   alpha 64   dropout .05", "targets 205 text linears",
    "  q,k,v,o,gate,up,down", "size ~193 MB"], BLUE, key="PK  adapter_id")

gpu = entity(s, 3.7, 3.55, 2.75, "GPU_HOST", "infra",
   ["NVIDIA L4   23 GB", "g2-standard-32  125 GB", "us-east1-c   spot",
    "~19.4 s/step  ~2h40m"], BLUE)

pred = entity(s, 7.05, 1.3, 3.15, "PREDICTION", "entity",
   ["model_id      FK", "raw_output    text",
    "parsed{break_type, action,", "       confidence, needs_human}"], RED,
   key="PK  exception_id + model_id")

gate = entity(s, 7.05, 3.35, 3.15, "SAFETY_GATE", "process",
   ["signals: onward movement,", "  account age, customer denial",
    "escalates only, never closes", "catches 62% of fraud",
    "holds 4% of clean cases"], RED)

scorer = entity(s, 7.05, 5.6, 3.15, "SCORER", "process",
   ["per-class accuracy", "confusion matrix",
    "confidence calibration", "deferral behaviour"], RED)

metrics = entity(s, 10.75, 1.3, 3.7, "METRICS", "entity",
   ["break_type_accuracy", "action_accuracy",
    "fraud_missed_pct", "fraud_MISSED_AND_AUTOCLOSED  <- the one",
    "unreadable_pct", "kept_and_answered_accuracy"], RED,
   key="PK  model_id")

syst = entity(s, 10.75, 3.5, 3.7, "SYSTEM_UNDER_TEST", "entity x4",
   ["1  rules engine        no AI", "2  E2B untrained       the before",
    "3  26B untrained       big, generic",
    "4  E2B fine-tuned      the product"], RED, key="PK  model_id")

deliver = entity(s, 3.7, 5.65, 2.75, "LAPTOP_BUILD", "artefact",
   ["merged   10.2 GB", "mlx 4-bit  ~2.5 GB", "local http, no network",
    "runs with wifi OFF"], PURPLE, key="PK  build_id")

link(s, base, lora, "fine-tuned into", "1 : 1")
link(s, trainer, lora, "produces", "1 : 1")
link(s, gpu, trainer, "hosts", "1 : N")
link(s, lora, pred, "answers with", "1 : N")
link(s, pred, gate, "passed through", "1 : 1")
link(s, gate, scorer, "then marked by", "N : 1")
link(s, pred, metrics, "aggregated into", "N : 1")
link(s, syst, metrics, "measured as", "1 : 1")
link(s, gpu, deliver, "merged into", "1 : 1")

note(s, "TRAIN (4000) reaches the TRAINER only. TEST (1000) reaches the SCORER only. "
        "Nothing crosses.\nThe test split never receives label noise — it is the ruler, "
        "and a bent ruler measures nothing.", 7.05, 7.35, 7.5, GREEN)
legend(s, 8.05)

prs.save("/Users/adg/Documents/LLM/exc2/training-erd.pptx")
print("saved 2 pages ->", "/Users/adg/Documents/LLM/exc2/training-erd.pptx")
