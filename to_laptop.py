"""Merge the adapter into the base model and shrink it for the demo laptop.

The LoRA adapter is a few tens of MB, but it needs the base model to run. This
merges the two into one set of weights, which mlx_lm can then convert to 4-bit
so the whole thing sits at roughly 2-3 GB and runs offline on an M-series Mac.

On the GPU box:      python3 to_laptop.py --merge
On the Mac:          python3 -m mlx_lm convert --hf-path out/merged \
                            --mlx-path out/merged-mlx -q --q-bits 4
"""
import argparse, os

HERE = os.path.dirname(os.path.abspath(__file__))


def merge(base, adapter, out):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel
    print("loading base...", flush=True)
    m = AutoModelForCausalLM.from_pretrained(base, dtype=torch.bfloat16)
    print("applying adapter...", flush=True)
    m = PeftModel.from_pretrained(m, adapter).merge_and_unload()
    os.makedirs(out, exist_ok=True)
    m.save_pretrained(out, safe_serialization=True)
    AutoTokenizer.from_pretrained(base).save_pretrained(out)
    total = sum(os.path.getsize(os.path.join(r, f))
                for r, _, fs in os.walk(out) for f in fs)
    print(f"merged -> {out}  ({total/1e9:.1f} GB)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--base", default="google/gemma-4-E2B-it")
    ap.add_argument("--adapter", default="out/lora")
    ap.add_argument("--out", default="out/merged")
    a = ap.parse_args()
    if a.merge:
        merge(a.base, a.adapter, a.out)
