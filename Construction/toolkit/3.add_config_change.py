import argparse
import json
import os
from numbers import Number


def is_scalar(v):
    return isinstance(v, (str, bool, Number)) or v is None


def diff_dicts(before, after, prefix=""):
    """Return list of change records between two dict-like objects."""
    changes = []
    before = before or {}
    after = after or {}

    # keys present
    all_keys = set()
    if isinstance(before, dict):
        all_keys.update(before.keys())
    if isinstance(after, dict):
        all_keys.update(after.keys())

    for key in sorted(all_keys):
        path = f"{prefix}.{key}" if prefix else key
        b = before.get(key) if isinstance(before, dict) else None
        a = after.get(key) if isinstance(after, dict) else None

        if key not in before:
            changes.append({"path": path, "type": "added", "before": None, "after": a})
        elif key not in after:
            changes.append({"path": path, "type": "removed", "before": b, "after": None})
        else:
            # both present
            if isinstance(b, dict) and isinstance(a, dict):
                changes.extend(diff_dicts(b, a, prefix=path))
            elif is_scalar(b) and is_scalar(a):
                if b != a:
                    note = None
                    if isinstance(b, Number) and isinstance(a, Number):
                        if a < b:
                            note = f"decreased by {b - a}"
                        else:
                            note = f"increased by {a - b}"
                    changes.append({"path": path, "type": "modified", "before": b, "after": a, "note": note})
            else:
                # fallback: if types differ or complex structures, compare by JSON
                if json.dumps(b, sort_keys=True, ensure_ascii=False) != json.dumps(a, sort_keys=True, ensure_ascii=False):
                    changes.append({"path": path, "type": "modified", "before": b, "after": a})

    return changes


def process_sample(sample):
    # work on sample copy
    s = dict(sample)
    # Support two common formats:
    # 1) multi-step: sample["trajectory"] is a list of items with config_before/config_after
    # 2) single-step: sample contains "step_detail" with config_before/config_after
    traj = s.get("trajectory")
    if isinstance(traj, list):
        items = traj
        container = "trajectory"
    elif "step_detail" in s:
        # wrap single step_detail as list so we can reuse logic
        items = [s.get("step_detail")]
        container = "step_detail"
    else:
        # nothing to do
        return s

    # ensure items is a list of dict-like
    processed_items = []
    for item in items:
        if not isinstance(item, dict):
            processed_items.append(item)
            continue

        before = item.get("config_before")
        after = item.get("config_after")
        changes = []
        if before is None and after is None:
            changes = []
        else:
            if not isinstance(before, dict) and before is not None:
                if before != after:
                    changes = [{"path": "", "type": "modified", "before": before, "after": after}]
                else:
                    changes = []
            else:
                changes = diff_dicts(before or {}, after or {})

        item["config_change"] = {"changes": changes, "change_count": len(changes)}
        processed_items.append(item)

    # put back processed items
    if container == "trajectory":
        s["trajectory"] = processed_items
    else:
        s["step_detail"] = processed_items[0] if processed_items else s.get("step_detail")

    return s


def load_input(path):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    try:
        data = json.loads(text)
        # if single sample dict, wrap
        if isinstance(data, dict) and "trajectory" in data:
            return [data]
        if isinstance(data, list):
            return data
    except Exception:
        # try JSONL
        items = []
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                items.append(json.loads(ln))
            except Exception:
                continue
        return items
    return []


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default="/EnvScaler/result/2.add_before_config_delete_some_message.jsonl")
    p.add_argument('-o', '--output', help='Output JSON file (pretty array)', default="/EnvScaler/result/3.add_config_change.json")
    args = p.parse_args()

    inp = args.input
    out = args.output or os.path.splitext(inp)[0] + '_with_changes.json'

    samples = load_input(inp)
    processed = [process_sample(s) for s in samples]

    with open(out, 'w', encoding='utf-8') as f:
        json.dump(processed, f, indent=2, ensure_ascii=False)

    print(f'Wrote {len(processed)} samples to {out}')


if __name__ == '__main__':
    main()
