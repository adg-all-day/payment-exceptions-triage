"""Run a model over the held-out cases and save what it said.

Two backends so the same script scores the small fine-tuned model and the big
untrained one:
    --backend hf       transformers, optionally with a LoRA adapter on top
    --backend ollama   whatever tag is pulled locally
"""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))


def load_cases(limit):
    rows = [json.loads(l) for l in
            open(os.path.join(HERE, "data", "test.jsonl")) if l.strip()]
    return rows[:limit] if limit else rows


def prompt_for(row):
    return row["instruction"] + "\n\nCASE:\n" + row["input"] + "\n\nJSON:"


def run_hf(args, rows):
    """Batched generation. One case at a time leaves the GPU mostly idle and
    turns a 1000-case pass into an hour; batching cuts it to minutes.

    Padding must go on the LEFT for decoder-only models, otherwise the pad
    tokens sit between the prompt and the answer and the model conditions on
    them."""
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    tok = AutoTokenizer.from_pretrained(args.model)
    tok.padding_side = "left"
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16, device_map="auto")
    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter).merge_and_unload()
    model.eval()

    # Long prompts first: batches then hold similar lengths and waste less
    # compute on padding. Original order is restored before writing.
    order = sorted(range(len(rows)),
                   key=lambda i: -len(rows[i]["input"]))
    out = [None] * len(rows)
    t0, done = time.time(), 0
    for b in range(0, len(order), args.batch):
        idxs = order[b:b + args.batch]
        texts = [tok.apply_chat_template(
                     [{"role": "user", "content": prompt_for(rows[i])}],
                     add_generation_prompt=True, tokenize=False) for i in idxs]
        enc = tok(texts, return_tensors="pt", padding=True, truncation=True,
                  max_length=args.maxlen, add_special_tokens=False).to(model.device)
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=args.max_new,
                                 do_sample=False, pad_token_id=tok.pad_token_id)
        for j, i in enumerate(idxs):
            out[i] = {"id": rows[i]["id"],
                      "output": tok.decode(gen[j][enc["input_ids"].shape[-1]:],
                                           skip_special_tokens=True)}
        done += len(idxs)
        el = time.time() - t0
        print(f"  {done}/{len(rows)}  {el/done:.2f}s/case  "
              f"eta {(len(rows)-done)*el/done/60:.1f}m", flush=True)
    return out


def run_ollama(args, rows):
    import urllib.request
    url = args.host.rstrip("/") + "/api/generate"
    out, t0 = [], time.time()
    for i, row in enumerate(rows, 1):
        # Gemma 4 26B reasons before answering. Left on, it spends the whole
        # token budget thinking and returns an empty response - the first run
        # scored 0% for exactly this reason, not because the model is bad.
        body = json.dumps({"model": args.model, "prompt": prompt_for(row),
                           "stream": False, "think": False,
                           "options": {"temperature": 0,
                                       "num_predict": args.max_new}}).encode()
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                text = json.loads(r.read())["response"]
        except Exception as e:
            text = ""
            print(f"  case {i} failed: {e}", file=sys.stderr)
        out.append({"id": row["id"], "output": text})
        if i % 10 == 0 or i == len(rows):
            el = time.time() - t0
            print(f"  {i}/{len(rows)}  {el/i:.2f}s/case  "
                  f"eta {(len(rows)-i)*el/i/60:.1f}m", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["hf", "ollama"], default="hf")
    ap.add_argument("--model", required=True)
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-new", dest="max_new", type=int, default=420)
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--maxlen", type=int, default=3072)
    args = ap.parse_args()
    rows = load_cases(args.limit)
    print(f"running {args.model}{' + ' + args.adapter if args.adapter else ''} "
          f"over {len(rows)} cases via {args.backend}", flush=True)
    res = run_hf(args, rows) if args.backend == "hf" else run_ollama(args, rows)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        for r in res:
            f.write(json.dumps(r) + "\n")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
