#!/usr/bin/env python3
"""
python3 11.retry_and_merge_wrapper.py \
  --prev-result /data/EnvScaler/interact_with_env/result/10.gemini-3.1-pro-preview_eval_results_20260329_154511.json \
  --input /data/EnvScaler/interact_with_env/result/9.choice_final_combined-167env.json \
  --output /data/EnvScaler/interact_with_env/result/gemini-final.json
"""

import argparse
import copy
import json
import os
import re
import time
from tqdm import tqdm
import openai

# Reuse utility functions from retry script (simplified)
def extract_json(text):
    if not isinstance(text, str):
        return None
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if m:
        inner = m.group(1).strip()
        try:
            return json.loads(inner)
        except Exception:
            try:
                import ast
                return ast.literal_eval(inner)
            except Exception:
                pass
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*?\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            try:
                import ast
                return ast.literal_eval(m.group(0))
            except Exception:
                return None
    return None

def parse_to_obj(value):
    if isinstance(value, (dict, list)):
        return value
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    obj = extract_json(value)
    if obj is not None:
        return obj
    try:
        import ast
        obj = ast.literal_eval(value)
        return obj
    except Exception:
        pass
    s = value.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        inner = s[1:-1]
        obj = extract_json(inner)
        if obj is not None:
            return obj
        try:
            import ast
            obj = ast.literal_eval(inner)
            return obj
        except Exception:
            pass
    return value

def action_to_call(action):
    if not isinstance(action, dict):
        return str(action)
    name = action.get('name') or action.get('action') or 'call'
    args = action.get('arguments') or action.get('args') or {}
    if isinstance(args, str):
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", args, re.IGNORECASE)
        if m:
            inner = m.group(1).strip()
            try:
                args = json.loads(inner)
            except Exception:
                try:
                    import ast
                    args = ast.literal_eval(inner)
                except Exception:
                    args = args
    try:
        arg_str = json.dumps(args, ensure_ascii=False)
    except Exception:
        arg_str = str(args)
    return f"{name}({arg_str})"

def diff_dicts(before, after, prefix=""):
    changes = []
    before = before or {}
    after = after or {}
    keys = set()
    if isinstance(before, dict):
        keys.update(before.keys())
    if isinstance(after, dict):
        keys.update(after.keys())
    for key in sorted(keys):
        path = f"{prefix}.{key}" if prefix else key
        b = before.get(key) if isinstance(before, dict) else None
        a = after.get(key) if isinstance(after, dict) else None
        if key not in before:
            changes.append({"path": path, "type": "added", "before": None, "after": a})
        elif key not in after:
            changes.append({"path": path, "type": "removed", "before": b, "after": None})
        else:
            if isinstance(b, dict) and isinstance(a, dict):
                changes.extend(diff_dicts(b, a, prefix=path))
            else:
                if b != a:
                    changes.append({"path": path, "type": "modified", "before": b, "after": a})
    return changes

def apply_change(obj, path, value, change_type):
    if not path:
        return False
    if isinstance(path, list):
        parts = [p for p in path]
    elif isinstance(path, str):
        parts = path.split('.')
    else:
        parts = [str(path)]
    cur = obj
    for p in parts[:-1]:
        if isinstance(cur, dict):
            key = p
            if key not in cur:
                cur[key] = {}
            cur = cur[key]
        elif isinstance(cur, list):
            try:
                idx = int(p)
            except Exception:
                return False
            while idx >= len(cur):
                cur.append({})
            cur = cur[idx]
        else:
            return False
    last = parts[-1]
    if change_type == 'delete' or change_type == 'removed':
        if isinstance(cur, dict):
            if last in cur:
                del cur[last]
                return True
            return False
        elif isinstance(cur, list):
            try:
                idx = int(last)
            except Exception:
                return False
            if 0 <= idx < len(cur):
                cur.pop(idx)
                return True
            return False
        else:
            return False
    else:
        if isinstance(cur, dict):
            cur[last] = value
            return True
        elif isinstance(cur, list):
            try:
                idx = int(last)
            except Exception:
                return False
            while idx >= len(cur):
                cur.append(None)
            cur[idx] = value
            return True
        else:
            return False

def evaluate_sample(step, model, temperature, openai_client, max_retries=2, thinking=False):
    cfg_before = step.get('config_before') or {}
    cfg_after = step.get('config_after') or {}
    env_code = step.get('env_code') or ''
    action = step.get('action')
    call_str = action_to_call(action)

    system_prompt = f"Environment code:\n\n{env_code}\n\nInitial config:\n{json.dumps(cfg_before, ensure_ascii=False, indent=2)}\n\nInstructions: You are given the environment code and the initial config. A tool call will be provided; you must predict the environment's textual feedback (exact output string) and any configuration changes that result from executing the tool. Only report config changes using types: add, modify, delete. Output ONLY a JSON object with keys: \"feedback\": string, \"config_changes\": [{{\"type\":..., \"path\":..., \"value\": ...}}]. If no config change, set \"config_changes\": []. Do not output other text."

    user_prompt = f"Tool call: {call_str}\n\nReturn the JSON as specified."
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

    resp_text = None
    for attempt in range(max_retries + 1):
        try:
            if thinking:
                resp = openai_client.chat.completions.create(
                    model=model, messages=messages, temperature=temperature, 
                    extra_body={"thinking": {"enabled": True}}, timeout=30
                )
            else:
                resp = openai_client.chat.completions.create(
                    model=model, messages=messages, temperature=temperature, timeout=30
                )
            resp_text = resp.choices[0].message.content
            break
        except Exception as e:
            if attempt >= max_retries:
                return {'error': f"API failed: {str(e)}"}
            time.sleep(5)

    parsed = extract_json(resp_text)
    if parsed is None:
        return {'error': 'failed_parse', 'raw': resp_text}

    feedback_pred_raw = parsed.get('feedback')
    changes_pred = parsed.get('config_changes', [])
    feedback_pred = parse_to_obj(feedback_pred_raw)

    pred_cfg = copy.deepcopy(cfg_before)
    for ch in changes_pred:
        ctype = ch.get('type')
        path = ch.get('path')
        val = ch.get('value') if 'value' in ch else ch.get('after')
        apply_change(pred_cfg, path, val, ctype)

    actual_changes = diff_dicts(cfg_before or {}, cfg_after or {})
    correct = True
    for a in actual_changes:
        p = a['path']
        parts = p.split('.')
        cur = pred_cfg
        ok = True
        for k in parts:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if not ok or cur != a.get('after'):
            correct = False
            break

    feedback_true_raw = step.get('observation', {}).get('content') if isinstance(step.get('observation'), dict) else step.get('observation')
    feedback_true = parse_to_obj(feedback_true_raw)
    feedback_match = (feedback_pred == feedback_true)

    return {
        'feedback_pred_raw': feedback_pred_raw,
        'feedback_true_raw': feedback_true_raw,
        'feedback_pred': feedback_pred,
        'feedback_true': feedback_true,
        'feedback_match': feedback_match,
        'changes_pred': changes_pred,
        'changes_true': actual_changes,
        'config_change_correct': correct,
        'predicted_after': pred_cfg,
    }

def load_input(path):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and ("trajectory" in data or "step_detail" in data):
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

def extract_steps(sample):
    steps = []
    env_code = sample.get('env_code') or sample.get('env') or sample.get('environment')
    if 'step_detail' in sample:
        sd = sample['step_detail']
        cc = None
        try:
            cc = (sd.get('config_change') or {}).get('change_count')
        except Exception:
            cc = None
        steps.append({
            'config_before': sd.get('config_before'),
            'config_after': sd.get('config_after'),
            'action': sd.get('action'),
            'env_code': env_code,
            'observation': sd.get('observation'),
            'change_count': cc,
        })
    elif 'trajectory' in sample and isinstance(sample['trajectory'], list):
        for it in sample['trajectory']:
            cc = None
            try:
                cc = (it.get('config_change') or {}).get('change_count')
            except Exception:
                cc = None
            steps.append({
                'config_before': it.get('config_before'),
                'config_after': it.get('config_after'),
                'action': it.get('action'),
                'env_code': env_code,
                'observation': it.get('observation'),
                'change_count': cc,
            })
    return steps

def get_arguments_count(step):
    action = step.get('action')
    if not isinstance(action, dict):
        return 0
    args = action.get('arguments') or action.get('args') or {}
    if isinstance(args, dict):
        return len(args.keys())
    elif isinstance(args, list):
        return len(args)
    else:
        try:
            parsed_args = json.loads(str(args))
            if isinstance(parsed_args, (dict, list)):
                return len(parsed_args)
        except Exception:
            pass
    return 0

def get_success_from_observation(step):
    obs = step.get('observation')
    if obs is None:
        return None
    if isinstance(obs, str):
        parsed = parse_to_obj(obs)
        if isinstance(parsed, dict):
            return parsed.get('success')
        return None
    if isinstance(obs, dict):
        content = obs.get('content')
        if content is not None:
            parsed = parse_to_obj(content)
            if isinstance(parsed, dict):
                return parsed.get('success')
        return None
    return None

def classify_step(step):
    success = get_success_from_observation(step)
    change_count = step.get('change_count')
    if success is False:
        return 'first_success_false'
    if success is True and change_count == 0:
        arg_cnt = get_arguments_count(step)
        if arg_cnt == 0:
            return 'first_change0_args0'
        elif arg_cnt == 1:
            return 'first_change0_args1'
        else:
            return None
    if change_count is not None:
        try:
            cc = int(change_count)
        except:
            return None
        if 1 <= cc <= 12:
            if cc == 1:
                return 'second_simple_1'
            elif cc == 2:
                return 'second_simple_2'
            elif cc == 3:
                return 'second_medium_3'
            elif cc == 4:
                return 'second_medium_4'
            elif cc == 5:
                return 'second_medium_5'
            elif cc == 6:
                return 'second_medium_6'
            elif 7 <= cc <= 12:
                return 'second_difficult_7_12'
    return None

def recalculate_summary(samples, results):
    categories = {
        'first_success_false': {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        'first_change0_args0': {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        'first_change0_args1': {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        'second_simple_1': {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        'second_simple_2': {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        'second_medium_3': {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        'second_medium_4': {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        'second_medium_5': {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        'second_medium_6': {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        'second_difficult_7_12': {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
    }
    first_total = {'count': 0, 'feedback_matches': 0, 'config_correct': 0}
    second_total = {'count': 0, 'feedback_matches': 0, 'config_correct': 0}
    overall_total = {'count': 0, 'feedback_matches': 0, 'config_correct': 0}
    
    simple_total = {'count': 0, 'feedback_matches': 0, 'config_correct': 0}
    medium_total = {'count': 0, 'feedback_matches': 0, 'config_correct': 0}
    difficult_sub = {i: {'count': 0, 'feedback_matches': 0, 'config_correct': 0} for i in range(7,13)}
    difficult_total = {'count': 0, 'feedback_matches': 0, 'config_correct': 0}

    sample_step_map = {}
    for s_idx, sample in enumerate(samples):
        steps = extract_steps(sample)
        for step_idx, step in enumerate(steps):
            sample_step_map[(s_idx, step_idx)] = step

    for item in results:
        s_idx = item['sample_index']
        step_idx = item['step_index']
        res = item.get('result', {})
        if 'error' in res:
            continue

        key = (s_idx, step_idx)
        if key not in sample_step_map:
            continue
        step = sample_step_map[key]

        fb_ok = 1 if res.get('feedback_match') else 0
        cfg_ok = 1 if res.get('config_change_correct') else 0
        cc_val = -1
        try:
            cc_val = int(item.get('change_count')) if item.get('change_count') is not None else -1
        except:
            cc_val = -1

        overall_total['count'] += 1
        overall_total['feedback_matches'] += fb_ok
        overall_total['config_correct'] += cfg_ok

        cat = classify_step(step)
        if cat and cat in categories:
            categories[cat]['count'] += 1
            categories[cat]['feedback_matches'] += fb_ok
            categories[cat]['config_correct'] += cfg_ok

            if cat.startswith('first'):
                first_total['count'] += 1
                first_total['feedback_matches'] += fb_ok
                first_total['config_correct'] += cfg_ok
            elif cat.startswith('second'):
                second_total['count'] += 1
                second_total['feedback_matches'] += fb_ok
                second_total['config_correct'] += cfg_ok

                if cat in ['second_simple_1', 'second_simple_2']:
                    simple_total['count'] += 1
                    simple_total['feedback_matches'] += fb_ok
                    simple_total['config_correct'] += cfg_ok
                elif cat in ['second_medium_3', 'second_medium_4', 'second_medium_5', 'second_medium_6']:
                    medium_total['count'] += 1
                    medium_total['feedback_matches'] += fb_ok
                    medium_total['config_correct'] += cfg_ok
                elif cat == 'second_difficult_7_12' and 7 <= cc_val <= 12:
                    difficult_sub[cc_val]['count'] += 1
                    difficult_sub[cc_val]['feedback_matches'] += fb_ok
                    difficult_sub[cc_val]['config_correct'] += cfg_ok
                    difficult_total['count'] += 1
                    difficult_total['feedback_matches'] += fb_ok
                    difficult_total['config_correct'] += cfg_ok

    # Calculate percentage
    for cat in categories:
        if categories[cat]['count'] > 0:
            categories[cat]['feedback_match_pct'] = categories[cat]['feedback_matches'] / categories[cat]['count'] * 100
            categories[cat]['config_correct_pct'] = categories[cat]['config_correct'] / categories[cat]['count'] * 100
        else:
            categories[cat]['feedback_match_pct'] = None
            categories[cat]['config_correct_pct'] = None

    for total_obj in [first_total, second_total, overall_total, simple_total, medium_total, difficult_total]:
        if total_obj['count'] > 0:
            total_obj['feedback_match_pct'] = total_obj['feedback_matches'] / total_obj['count'] * 100
            total_obj['config_correct_pct'] = total_obj['config_correct'] / total_obj['count'] * 100
        else:
            total_obj['feedback_match_pct'] = None
            total_obj['config_correct_pct'] = None

    for key in difficult_sub:
        if difficult_sub[key]['count'] > 0:
            difficult_sub[key]['feedback_match_pct'] = difficult_sub[key]['feedback_matches'] / difficult_sub[key]['count'] * 100
            difficult_sub[key]['config_correct_pct'] = difficult_sub[key]['config_correct'] / difficult_sub[key]['count'] * 100
        else:
            difficult_sub[key]['feedback_match_pct'] = None
            difficult_sub[key]['config_correct_pct'] = None

    return {
        'first_category': {
            'subcategories': {
                'success_false': categories['first_success_false'],
                'change0_args0': categories['first_change0_args0'],
                'change0_args1': categories['first_change0_args1']
            },
            'total': first_total
        },
        'second_category': {
            'subcategories': {
                'simple_1': categories['second_simple_1'],
                'simple_2': categories['second_simple_2'],
                'medium_3': categories['second_medium_3'],
                'medium_4': categories['second_medium_4'],
                'medium_5': categories['second_medium_5'],
                'medium_6': categories['second_medium_6'],
                'difficult_7_12': categories['second_difficult_7_12']
            },
            'total': second_total
        },
        'overall': overall_total,
        'custom_summary': {
            'simple_total': simple_total,
            'medium_total': medium_total,
            'difficult_sub': difficult_sub,
            'difficult_total': difficult_total
        }
    }

def find_failed(prev_result_path):
    with open(prev_result_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    results = data.get('results', [])
    failed = []
    for it in results:
        s_idx = it.get('sample_index')
        step_idx = it.get('step_index')
        res = it.get('result')
        if res is None:
            failed.append((s_idx, step_idx))
            continue
        if isinstance(res, dict) and 'error' in res:
            failed.append((s_idx, step_idx))
            continue
        if isinstance(res, str) and ("Error code" in res or "API failed" in res or "MODEL_CAPACITY_EXHAUSTED" in res):
            failed.append((s_idx, step_idx))
            continue
    return failed

def write_failed_list(failed, path):
    with open(path, 'w', encoding='utf-8') as f:
        for s, st in failed:
            f.write(f"{s},{st}\n")

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--prev-result', default='/EnvScaler/result/10.gemini-3.1-pro-preview_eval_results_20260329_154511.json')
    p.add_argument('--input', default='/EnvScaler/result/9.choice_final_combined-167env.json')
    p.add_argument('--model', default='gemini-3.1-pro-preview')
    p.add_argument('--temperature', type=float, default=0.0)
    p.add_argument('--thinking', type=bool, default=False)
    p.add_argument('--output', default='/EnvScaler/result/10.gemini-final.json')
    p.add_argument('--toolkit-dir', default='/dEnvScaler/result/toolkit')
    p.add_argument('--dry-run', action='store_true', help='Only detect failed samples and write failed list, do not rerun')
    p.add_argument('--limit', type=int, default=1, help='Limit number of failed samples to rerun (0=no limit)')
    p.add_argument('--resume', type=int, default=0, help='Skip first N failed samples when rerunning')
    args = p.parse_args()

    if 'OPENAI_API_KEY' not in os.environ:
        print("❌ Please set OPENAI_API_KEY environment variable first")
        return
    openai.api_key = os.environ['OPENAI_API_KEY']

    failed = find_failed(args.prev_result)
    if not failed:
        print("No failed samples found in prev-result. Nothing to do.")
        return

    failed_list_path = os.path.join(args.toolkit_dir, 'failed_auto.txt')
    write_failed_list(failed, failed_list_path)
    print(f"Detected {len(failed)} failed samples -> {failed_list_path}")

    if args.dry_run:
        print("Dry-run: detected failures written; exiting without rerun.")
        return

    # Load old result and remove failed entries
    with open(args.prev_result, 'r', encoding='utf-8') as f:
        prev = json.load(f)
    old_results = prev.get('results', [])
    new_results = [it for it in old_results if (it.get('sample_index'), it.get('step_index')) not in set(failed)]

    samples = load_input(args.input)
    retry_tasks = []
    for s_idx, sample in enumerate(samples):
        steps = extract_steps(sample)
        for step_idx, step in enumerate(steps):
            if (s_idx, step_idx) in set(failed):
                retry_tasks.append((s_idx, step_idx, step))
    # apply resume/limit
    total_retry = len(retry_tasks)
    if args.resume > 0:
        retry_tasks = retry_tasks[args.resume:]
    if args.limit > 0:
        retry_tasks = retry_tasks[:args.limit]
    print(f"🚀 Retrying {len(retry_tasks)} / {total_retry} failed tasks (resume={args.resume}, limit={args.limit})\n")

    pbar = tqdm(total=len(retry_tasks), desc="Retrying failed tasks")
    try:
        for s_idx, step_idx, step in retry_tasks:
            res = evaluate_sample(step, args.model, args.temperature, openai, thinking=args.thinking)
            new_results.append({
                "sample_index": s_idx,
                "step_index": step_idx,
                "change_count": step.get('change_count'),
                "result": res
            })
            pbar.update(1)
    except KeyboardInterrupt:
        pbar.close()
        partial_path = args.output + '.partial.json'
        print('\nInterrupted by user — saving partial results to', partial_path)
        prev['results'] = new_results
        prev['summary'] = recalculate_summary(samples, new_results)
        with open(partial_path, 'w', encoding='utf-8') as f:
            json.dump(prev, f, indent=2, ensure_ascii=False)
        print('Partial save complete. You can resume with --resume to skip completed samples.')
        return
    finally:
        try:
            pbar.close()
        except Exception:
            pass

    print("\n📊 Recalculating overall statistics...")
    new_summary = recalculate_summary(samples, new_results)
    prev['results'] = new_results
    prev['summary'] = new_summary

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(prev, f, indent=2, ensure_ascii=False)

    print(f"\n🎉 Task completed successfully. Merged result saved to: {args.output}")

if __name__ == '__main__':
    main()
