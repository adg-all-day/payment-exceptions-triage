"""Emit a page showing training examples verbatim, prompt beside response."""
import json, html, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
rows = [json.loads(l) for l in open(os.path.join(HERE, "data/train.jsonl"))]
import textpool as tp

def pick():
    out = []
    def take(pred, why):
        for r in rows:
            if pred(r):
                out.append((r, why)); return
    take(lambda r: r["true_break"] == "NO_BREAK"
         and tp.subcause_of(json.loads(r["input"])) == "fee",
         "Looks like money went missing. It is the transfer charge plus VAT. "
         "A rules engine comparing two numbers calls this a break.")
    take(lambda r: r["true_break"] == "NO_BREAK"
         and tp.subcause_of(json.loads(r["input"])) == "name",
         "Two different spellings of the same person. String comparison says "
         "mismatch; a reader says same person.")
    take(lambda r: r["true_break"] == "NO_BREAK"
         and tp.subcause_of(json.loads(r["input"])) == "two",
         "Two debits, same amount, same day - but two genuine transfers, not a "
         "duplicate. Different references.")
    take(lambda r: r["true_break"] == "SUSPECTED_FRAUD"
         and json.loads(r["input"]).get("onward_transfers"),
         "Fraud with the fan-out listed as structured data. The easy case.")
    take(lambda r: r["true_break"] == "SUSPECTED_FRAUD"
         and not json.loads(r["input"]).get("onward_transfers"),
         "Same fraud, but the fan-out is described in the remarks log in "
         "ordinary English. This is the one regexes lose.")
    take(lambda r: r["true_break"] == "REVERSAL_NOT_APPLIED"
         and not r["ambiguous"],
         "The refund reference is buried in the remarks. Untrained Gemma scored "
         "6.4% on this class; fine-tuned scored 73-80%.")
    take(lambda r: r["ambiguous"],
         "Evidence deliberately removed. The only correct answer is to hand it "
         "to a human - and saying so confidently is the skill.")
    return out

CSS = """
:root{--ground:#FBFCFB;--surface:#fff;--sunk:#F1F5F2;--ink:#14201B;--body:#28352F;
 --muted:#5E6E67;--faint:#8B9A93;--line:#DEE6E1;--rule:#C6D2CB;
 --acc:#0E6B4F;--acc-soft:#E4F0EA;--blue:#1E4E8C;--blue-soft:#E7EEF7;
 --amber:#8A6A12;--amber-soft:#F8F1DE;--red:#B3341F;--red-soft:#FBEAE6;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
 --ground:#0E1412;--surface:#151C19;--sunk:#1A2320;--ink:#E8EEEA;--body:#C6D2CC;
 --muted:#93A29B;--faint:#6C7B74;--line:#242E2A;--rule:#33403A;
 --acc:#46C395;--acc-soft:#12291F;--blue:#7FB0EA;--blue-soft:#131E2C;
 --amber:#D8B45E;--amber-soft:#291F13;--red:#F08A72;--red-soft:#2A1712;}}
:root[data-theme="dark"]{
 --ground:#0E1412;--surface:#151C19;--sunk:#1A2320;--ink:#E8EEEA;--body:#C6D2CC;
 --muted:#93A29B;--faint:#6C7B74;--line:#242E2A;--rule:#33403A;
 --acc:#46C395;--acc-soft:#12291F;--blue:#7FB0EA;--blue-soft:#131E2C;
 --amber:#D8B45E;--amber-soft:#291F13;--red:#F08A72;--red-soft:#2A1712;}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--body);
 font-family:"Public Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
 font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.wrap{max-width:1500px;margin:0 auto;padding:0 22px 90px}
h1,h2{font-family:"Public Sans",sans-serif;color:var(--ink);margin:0;
 letter-spacing:-.02em;text-wrap:balance}
header{padding:60px 0 26px;border-bottom:2px solid var(--ink)}
.eyebrow{font-size:11.5px;letter-spacing:.15em;text-transform:uppercase;
 font-weight:700;color:var(--acc);margin-bottom:14px}
h1{font-size:clamp(30px,4.4vw,46px);line-height:1.05;font-weight:800}
.lede{color:var(--muted);max-width:78ch;margin-top:14px;font-size:16.5px}
.key{display:flex;flex-wrap:wrap;gap:8px 20px;margin-top:22px;font-size:13px}
.key i{font-style:normal;display:inline-flex;align-items:center;gap:7px;color:var(--muted)}
.sw{width:11px;height:11px;border-radius:3px;display:inline-block}
section{margin-top:44px}
.cap{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;margin-bottom:9px}
.num{font-family:"JetBrains Mono",monospace;font-size:12px;color:var(--faint);
 font-weight:600}
h2{font-size:19px;font-weight:700}
.tag{font-family:"JetBrains Mono",monospace;font-size:11px;font-weight:600;
 padding:3px 9px;border-radius:99px;background:var(--acc-soft);color:var(--acc)}
.tag.amb{background:var(--amber-soft);color:var(--amber)}
.why{color:var(--muted);font-size:14.5px;max-width:96ch;margin:0 0 13px}
table{width:100%;border-collapse:separate;border-spacing:0;
 background:var(--surface);border:1px solid var(--line);border-radius:11px;
 overflow:hidden;table-layout:fixed}
th{text-align:left;font-size:11px;letter-spacing:.13em;text-transform:uppercase;
 padding:11px 15px;color:#fff;font-weight:700}
th.p{background:var(--acc)} th.r{background:var(--blue)}
td{vertical-align:top;padding:0;border-top:1px solid var(--line);width:50%}
td:first-child{border-right:1px solid var(--line)}
pre{margin:0;padding:15px 17px;font-family:"JetBrains Mono",ui-monospace,Menlo,
 monospace;font-size:11.5px;line-height:1.5;white-space:pre-wrap;
 word-break:break-word;overflow-x:auto;max-height:460px;overflow-y:auto;
 color:var(--body)}
pre.instr{background:var(--sunk);color:var(--muted);max-height:none;
 border-bottom:1px dashed var(--rule);font-size:11px}
b.ev{color:var(--acc);font-weight:600}
b.ag{color:var(--amber);font-weight:600}
b.an{color:var(--blue);font-weight:600}
.foot{margin-top:56px;padding-top:22px;border-top:2px solid var(--ink);
 color:var(--faint);font-size:13.5px}
@media(max-width:900px){table,thead,tbody,tr,td,th{display:block;width:100%}
 td:first-child{border-right:0}}
"""

def esc(t): return html.escape(t)

def mark_input(t):
    """Green = evidence the answer must rest on. Amber = agent-written prose."""
    t = esc(t)
    for k in ("customer_complaint", "remarks"):
        t = t.replace(f'"{k}"', f'<b class="ag">"{k}"</b>')
    for k in ("ledger", "switch", "settlement_file_line", "onward_transfers",
              "name_enquiry", "reversal", "amount_ngn"):
        t = t.replace(f'"{k}"', f'<b class="ev">"{k}"</b>')
    return t

def mark_out(t):
    t = esc(t)
    for k in ("break_type", "action", "needs_human", "confidence"):
        t = t.replace(f'"{k}"', f'<b class="an">"{k}"</b>')
    for k in ("money_trace", "analyst_note"):
        t = t.replace(f'"{k}"', f'<b class="ag">"{k}"</b>')
    return t

items = pick()
out = ['<title>Training Examples, Verbatim</title>',
 '<link rel="preconnect" href="https://fonts.googleapis.com">',
 '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
 '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
 'family=Public+Sans:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600'
 '&display=swap">',
 f'<style>{CSS}</style>', '<div class="wrap">',
 '<header><div class="eyebrow">Payments exceptions model &middot; training set</div>',
 '<h1>What the model is actually shown</h1>',
 '<p class="lede">Seven examples straight out of <code>data/train.jsonl</code>, '
 'unedited. Left is the prompt, right is the answer it must learn to produce. '
 'Loss is computed on the right-hand side only &mdash; learning to echo the case '
 'back would waste the gradient on text we already have.</p>',
 '<div class="key">'
 '<i><span class="sw" style="background:var(--acc)"></span>evidence the answer must rest on</i>'
 '<i><span class="sw" style="background:var(--amber)"></span>written by an agent, not by code</i>'
 '<i><span class="sw" style="background:var(--blue)"></span>the decision being learned</i>'
 '</div></header>']

for i, (r, why) in enumerate(items, 1):
    amb = ' <span class="tag amb">must defer</span>' if r["ambiguous"] else ''
    out.append(f'<section><div class="cap"><span class="num">{i:02d}</span>'
               f'<h2>{esc(r["true_break"].replace("_"," ").title())}</h2>'
               f'<span class="tag">{esc(r["id"])}</span>{amb}</div>'
               f'<p class="why">{esc(why)}</p>'
               f'<table><thead><tr><th class="p">Prompt &mdash; what it is shown</th>'
               f'<th class="r">Response &mdash; what it must output</th></tr></thead>'
               f'<tbody><tr><td>'
               f'<pre class="instr">{esc(r["instruction"])}</pre>'
               f'<pre>{mark_input(r["input"])}</pre></td>'
               f'<td><pre>{mark_out(json.dumps(r["target"], indent=1))}</pre>'
               f'</td></tr></tbody></table></section>')

out.append('<div class="foot"><p><b>All of it is invented.</b> No real bank, '
 'customer or transaction appears anywhere. The records are generated by code so '
 'the correct answer is certain; the human prose is written by language models so '
 'the evidence cannot simply be pattern-matched. Neither half works alone &mdash; '
 'templated prose let a plain rules engine score 96.6%, and deleting the prose '
 'left 47% of fraud cases unanswerable.</p>'
 '<p>Set fingerprint <code>4ba6c7ab39dd</code> &middot; 4,000 training rows, '
 '1,000 held back.</p></div></div>')

open(os.path.join(HERE, "training-examples.html"), "w").write("\n".join(out))
print("wrote training-examples.html", len("\n".join(out)) // 1024, "KB",
      "|", len(items), "examples")
