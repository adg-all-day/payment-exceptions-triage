"""Collect the text each agent wrote and save it as clean JSON pools."""
import json, os, re, sys, glob

SIDE_A = {
    "a414e1ad1171057d8": "NO_BREAK",
    "ac2ae082b916e1c7f": "SWITCH_TIMEOUT_NO_REVERSAL",
    "ae590598e15fae6b7": "DUPLICATE_POSTING",
    "a2130994688f26113": "REVERSAL_NOT_APPLIED",
    "a507ce907c659c912": "WRONG_BENEFICIARY",
    "a0d61e0b60c6bc456": "PARTIAL_SETTLEMENT",
    "a19a43e2045703978": "SUSPECTED_FRAUD",
}
SIDE_B = {
    "ae01d008114ef1840": "NO_BREAK",
    "ae8a05d977ac0356c": "SWITCH_TIMEOUT_NO_REVERSAL",
    "a374a2f2e0ce3d576": "DUPLICATE_POSTING",
    "a364d00dd2c15dcd1": "REVERSAL_NOT_APPLIED",
    "a27dd16987b7383c3": "WRONG_BENEFICIARY",
    "afeea9e6885f658d0": "PARTIAL_SETTLEMENT",
    "a6544a3939d38d4f3": "SUSPECTED_FRAUD",
}
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "text")


def biggest_json(text):
    best = None
    for m in re.finditer(r"\{", text):
        start = m.start()
        depth, in_str, esc = 0, False, False
        for i, ch in enumerate(text[start:], start):
            if in_str:
                if esc: esc = False
                elif ch == "\\": esc = True
                elif ch == '"': in_str = False
                continue
            if ch == '"': in_str = True
            elif ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        d = json.loads(text[start:i + 1])
                    except Exception:
                        break
                    if isinstance(d, dict) and (
                            {"complaints", "remarks"} <= set(d) or
                            {"traces", "notes"} <= set(d)):
                        if best is None or len(text[start:i + 1]) > best[0]:
                            best = (len(text[start:i + 1]), d)
                    break
    return best[1] if best else None


def harvest(path):
    texts = []
    with open(path, errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            content = (rec.get("message") or {}).get("content")
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for blk in content:
                    if isinstance(blk, dict) and blk.get("type") == "text":
                        texts.append(blk.get("text", ""))
                    elif isinstance(blk, str):
                        texts.append(blk)
    for t in reversed(texts):
        d = biggest_json(t)
        if d:
            return d
    return biggest_json("\n".join(texts))


def main(tasks_dir):
    os.makedirs(OUT, exist_ok=True)
    ok, missing = 0, []
    for table, side in ((SIDE_A, "in"), (SIDE_B, "out")):
        for aid, kind in table.items():
            hits = glob.glob(os.path.join(tasks_dir, aid + "*"))
            if not hits:
                missing.append(f"{kind}/{side} (no file)"); continue
            d = harvest(hits[0])
            if not d:
                missing.append(f"{kind}/{side} (unparsed)"); continue
            fixed = {k: [s.replace("\\n", " ").strip() for s in v
                         if isinstance(s, str) and s.strip()] for k, v in d.items()}
            json.dump(fixed, open(os.path.join(OUT, f"{kind}.{side}.json"), "w"),
                      indent=1, ensure_ascii=False)
            ok += 1
    print(f"harvested {ok}/14")
    for m in missing:
        print("  missing:", m)


if __name__ == "__main__":
    main(sys.argv[1])
