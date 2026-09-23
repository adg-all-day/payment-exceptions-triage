#!/usr/bin/env bash
# Everything that happens after training. One command.
set -uo pipefail
cd /home/adg/exceptions
export OLLAMA_HOST=127.0.0.1:11434

echo "=== 1/4  fine-tuned E2B ==========================================="
python3 -u run_model.py --backend hf --model google/gemma-4-E2B-it \
        --adapter out/lora --out out/preds_tuned.jsonl --batch 16

echo "=== 2/4  SAME model untrained (the before picture) ================"
python3 -u run_model.py --backend hf --model google/gemma-4-E2B-it \
        --out out/preds_base.jsonl --batch 16

echo "=== 3/4  26B untrained (big vs small) ============================="
pgrep -x ollama >/dev/null || (setsid nohup ollama serve >/tmp/ollama.log 2>&1 </dev/null &) && sleep 6
python3 -u run_model.py --backend ollama --model gemma4:26b-a4b-it-qat \
        --out out/preds_26b.jsonl

echo "=== 4/4  merge for the laptop ====================================="
python3 -u to_laptop.py --merge

echo "=== SCORES ========================================================"
python3 score.py out/preds_rules.jsonl out/preds_base.jsonl \
                 out/preds_26b.jsonl out/preds_tuned.jsonl
echo "ALL DONE"
