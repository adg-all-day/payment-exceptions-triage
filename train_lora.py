"""Fine-tune Gemma on the exception cases with LoRA.

LoRA freezes the model's own weights and trains a small set of extra ones
alongside. Cheap, fast, and the result is a few tens of MB that can be carried
to the demo laptop.
"""
import argparse, json, os
import torch
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig

HERE = os.path.dirname(os.path.abspath(__file__))


def build(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    return Dataset.from_list([{
        "messages": [
            {"role": "user",
             "content": r["instruction"] + "\n\nCASE:\n" + r["input"] + "\n\nJSON:"},
            {"role": "assistant",
             "content": json.dumps(r["target"], ensure_ascii=False)}]}
        for r in rows])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="google/gemma-4-E2B-it")
    ap.add_argument("--out", default="out/lora")
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--bs", type=int, default=1)
    ap.add_argument("--accum", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--maxlen", type=int, default=3072)
    args = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(args.model)
    ds = build(os.path.join(HERE, "data", "train.jsonl"))
    print(f"{len(ds)} training examples", flush=True)

    model = AutoModelForCausalLM.from_pretrained(
        args.model, dtype=torch.bfloat16, device_map="auto",
        attn_implementation="eager")
    model.config.use_cache = False

    # Gemma 4 E2B wraps the VISION tower's linears in Gemma4ClippableLinear,
    # which LoRA cannot attach to - and which we do not want anyway, since this
    # task is text only. So target the text decoder layers by path.
    peft = LoraConfig(
        r=32, lora_alpha=64, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM",
        target_modules=r"^model\.language_model\.layers\.\d+\."
                       r"(self_attn|mlp)\."
                       r"(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)$")

    cfg = SFTConfig(
        output_dir=args.out, num_train_epochs=args.epochs,
        per_device_train_batch_size=args.bs,
        gradient_accumulation_steps=args.accum,
        learning_rate=args.lr, lr_scheduler_type="cosine", warmup_steps=15,
        logging_steps=10, save_strategy="epoch", bf16=True,
        max_length=args.maxlen, gradient_checkpointing=True,
        report_to=[], packing=False,
        # Train on the answer only - parroting the case back would waste most
        # of the gradient on text we already have.
        completion_only_loss=True)

    trainer = SFTTrainer(model=model, args=cfg, train_dataset=ds,
                         processing_class=tok, peft_config=peft)
    trainer.train()
    trainer.save_model(args.out)
    tok.save_pretrained(args.out)
    print("saved adapter to", args.out)


if __name__ == "__main__":
    main()
