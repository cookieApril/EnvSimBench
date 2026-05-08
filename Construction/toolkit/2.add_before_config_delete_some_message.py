import argparse
import json
import os
import copy


def process_sample(sample):
    # Build task_info: preserve existing if present, otherwise keep all top-level keys except trajectory
    if "task_info" in sample:
        task_info = sample["task_info"]
    else:
        task_info = {k: v for k, v in sample.items() if k != "trajectory"}

    trajectory = sample.get("trajectory", [])
    # find initial config (from step 0 if present)
    last_config = None
    for item in trajectory:
        if item.get("step", 0) == 0 and "config" in item:
            last_config = copy.deepcopy(item.get("config"))
            break

    processed_traj = []
    for item in trajectory:
        step = item.get("step", None)
        action = item.get("action", None)
        if step is None:
            continue
        if step == 0:
            # skip step 0 in output but keep its config as last_config
            if "config" in item:
                last_config = copy.deepcopy(item.get("config"))
            continue

        config_after = copy.deepcopy(item.get("config")) if item.get("config") is not None else None
        config_before = copy.deepcopy(last_config) if last_config is not None else None

        # If config_after is missing, assume no change (use config_before)
        if config_after is None and config_before is not None:
            config_after = copy.deepcopy(config_before)

        processed_item = {
            "step": step,
            "action": action,
            "observation": item.get("observation"),
            "config_before": config_before,
            "config_after": config_after,
        }

        processed_traj.append(processed_item)

        # update last_config to be config_after for next iteration
        if config_after is not None:
            last_config = copy.deepcopy(config_after)

    return {"task_info": task_info, "trajectory": processed_traj}


def process_file(inpath, outpath):
    with open(inpath, "r", encoding="utf-8") as f:
        text = f.read()

    # Try to parse as JSON list or JSON object; fallback to JSONL
    try:
        data = json.loads(text)
    except Exception:
        # assume JSONL
        data = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except Exception:
                # skip invalid lines
                continue

    # If top-level is dict but contains many samples under a key (rare), try to detect
    samples = []
    if isinstance(data, list):
        samples = data
    elif isinstance(data, dict):
        # if dict looks like a single sample (has trajectory), treat as single
        if "trajectory" in data:
            samples = [data]
        else:
            # otherwise no clear samples; write nothing
            print(f"No trajectory found in {inpath}; skipping")
            return

    # write output as JSONL (one processed sample per line)
    os.makedirs(os.path.dirname(outpath) or ".", exist_ok=True)
    with open(outpath, "w", encoding="utf-8") as out_f:
        for sample in samples:
            processed = process_sample(sample)
            out_f.write(json.dumps(processed, ensure_ascii=False) + "\n")


def main():
    p = argparse.ArgumentParser(description="Analyze config changes per step and produce simplified trajectories.")
    p.add_argument('--input', default="/EnvScaler/result/1.tra_3458sample.json") #JSON file generated from file 1
    p.add_argument('-o', '--output', help='Output JSON file (pretty array)', default="/EnvScaler/result/2.add_before_config_delete_some_message.jsonl")
    args = p.parse_args()

    inpath = args.input
    if not os.path.isfile(inpath):
        raise SystemExit(f"Input file not found: {inpath}")

    outpath = args.output
    if not outpath:
        base = os.path.splitext(os.path.basename(inpath))[0]
        outpath = os.path.join(os.path.dirname(inpath), base + "_config_changes.jsonl")

    process_file(inpath, outpath)
    print(f"Wrote processed samples to {outpath}")


if __name__ == "__main__":
    main( )
