import argparse
import json
import os


def load_input(path):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "trajectory" in data:
            return [data]
        if isinstance(data, list):
            return data
    except Exception:
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


def add_sample_ids(samples, start=1, width=3):
    for i, s in enumerate(samples, start=start):
        sid = f"{i:0{width}d}"
        if isinstance(s, dict):
            ti = s.get('task_info')
            if ti is None or not isinstance(ti, dict):
                s['task_info'] = {'sample_id': sid}
            else:
                ti['sample_id'] = sid
    return samples


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default="C:\\Users\\cookie\\Desktop\\EnvScaler\\interact_with_env\\result\\single_round_samples.json")
    p.add_argument('-o', '--output', help='Output JSON file (pretty array)', default=None)
    p.add_argument('--start', type=int, default=1, help='Starting index')
    p.add_argument('--width', type=int, default=3, help='Zero-pad width')
    args = p.parse_args()

    inp = args.input
    out = args.output or os.path.splitext(inp)[0] + '_with_ids.json'

    samples = load_input(inp)
    if not samples:
        print(f'No samples loaded from {inp}.')
        return

    processed = add_sample_ids(samples, start=args.start, width=args.width)

    with open(out, 'w', encoding='utf-8') as f:
        json.dump(processed, f, indent=2, ensure_ascii=False)

    print(f'Wrote {len(processed)} samples to {out}')


if __name__ == '__main__':
    main()
