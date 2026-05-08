import argparse
import json
import os
import time
import copy
import re
import sys
import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# ====================== Checkpoint Resume Utility Functions (New) ======================
def load_checkpoint(checkpoint_path):
    """Load checkpoint file, return set of completed (sample_index, step_index)"""
    completed = set()
    if not os.path.exists(checkpoint_path):
        return completed
    try:
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data.get("completed", []):
                if isinstance(item, list) and len(item) == 2:
                    completed.add((item[0], item[1]))
    except Exception as e:
        print(f"⚠️ Failed to load checkpoint, will start evaluation from scratch: {str(e)}", file=sys.stderr)
    return completed

def save_checkpoint(checkpoint_path, completed_tasks):
    """Save checkpoint file, write completed task list"""
    try:
        data = {
            "completed": [[s_idx, step_idx] for s_idx, step_idx in completed_tasks],
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Failed to save checkpoint: {str(e)}", file=sys.stderr)
# ======================================================================

try:
    import openai
except Exception:
    openai = None

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    class SimpleProgress:
        def __init__(self, total, desc='Processing', unit='step'):
            self.total = total
            self.desc = desc
            self.unit = unit
            self.current = 0
            self.last_percent = 0
            print(f"{desc}: 0%", end='')
        def update(self, n=1):
            self.current += n
            if self.total <= 0:
                return
            percent = int(self.current / self.total * 100)
            if percent > self.last_percent:
                self.last_percent = percent
                print(f"\r{self.desc}: {percent}%", end='')
        def close(self):
            print()
    tqdm = SimpleProgress


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

    # system_prompt = f"""Environment Code:{env_code}

    # Initial Configuration:
    # {json.dumps(cfg_before, ensure_ascii=False, indent=2)}

    # # STRICT TASK INSTRUCTIONS (MUST COMPLY 100%)
    # 1.  Given the environment code and initial config, you need to **simulate the complete execution result of the tool call**.
    # 2.  Output the **FULL, EXACT, UNMODIFIED textual feedback string** that the environment returns after running the tool. This must include all fields (success status, error messages, return values, etc.) — DO NOT omit, simplify, or leave empty.
    # 3.  Predict all configuration changes caused by the tool. Only use 3 change types: add, modify, delete.
    # 4.  Output **ONLY a valid JSON object**, NO extra text, NO explanations, NO markdown blocks.
    # 5.  JSON FORMAT (fixed keys):
    # - "feedback": string (the complete environment output, full text, no truncation)
    # - "config_changes": list of objects (each with "type", "path", "value"; empty list if no changes)"""
   
    user_prompt = f"Tool call: {call_str}\n\nReturn the JSON as specified."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    resp_text = None
    for attempt in range(max_retries + 1):
        try:
            if thinking:
                resp = openai_client.chat.completions.create(model=model, messages=messages, temperature=temperature, extra_body={"thinking": {"type": "enabled"}})
                resp_text = resp.choices[0].message.content
            else:
                resp = openai_client.chat.completions.create(model=model, messages=messages, temperature=temperature)
                resp_text = resp.choices[0].message.content
                break
        except Exception as e:
            if attempt >= max_retries:
                return {'error': str(e)}
            time.sleep(1)

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
        if not ok:
            correct = False
            break
        if cur != a.get('after'):
            correct = False
            break

    feedback_true_raw = None
    obs = step.get('observation')
    if isinstance(obs, dict):
        feedback_true_raw = obs.get('content')
    else:
        feedback_true_raw = obs

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


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default='/EnvScaler/result/9.choice_final_combined-167env.json')
    p.add_argument('-o', '--output', default=None, help='Output JSON file')
    p.add_argument('--model', default='gemini-3.1-pro-preview')
    p.add_argument('--temperature', type=float, default=0.0)
    p.add_argument('--max_samples', type=int, default=400)
    p.add_argument('--max_workers', type=int, default=5)
    p.add_argument('--thinking', type=bool, default=False)
    p.add_argument('--checkpoint', default=None, help='Checkpoint file path for resuming evaluation')
    # =========================================================
    args = p.parse_args()

    if openai is None:
        print('openai package not available; pip install openai')
        return
    if 'OPENAI_API_KEY' not in os.environ:
        print('Please set OPENAI_API_KEY in environment')
        return

    openai.api_key = os.environ['OPENAI_API_KEY']
    openai_client = openai

    if args.output is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_model = args.model.replace('/', '_')
        args.output = f'/EnvScaler/result/10.{safe_model}_eval_results_{timestamp}.json'

    # ====================== Initialize Checkpoint (New) ======================
    if args.checkpoint is None:
        # Auto-generate checkpoint path (same directory as output file)
        base_dir = os.path.dirname(args.output)
        os.makedirs(base_dir, exist_ok=True)
        args.checkpoint = os.path.join(base_dir, "eval_checkpoint.json")
    # Load completed tasks
    completed_tasks = load_checkpoint(args.checkpoint)
    print(f"✅ Checkpoint loaded: {len(completed_tasks)} evaluation steps completed")
    # ==============================================================

    samples = []
    try:
        items = load_input(args.input)
        for it in items:
            if isinstance(it, dict):
                samples.append(it)
    except Exception as e:
        print(f'Error loading input {args.input}: {e}', file=sys.stderr)
        return

    # 1. Collect all pending tasks + filter completed ones
    tasks = []
    task_count = 0
    for s_idx, sample in enumerate(samples):
        steps = extract_steps(sample)
        for step_idx, step in enumerate(steps):
            if args.max_samples and task_count >= args.max_samples:
                break
            # Skip completed tasks
            if (s_idx, step_idx) in completed_tasks:
                continue
            tasks.append((s_idx, step_idx, step))
            task_count += 1
    total_steps = len(tasks)
    if total_steps == 0:
        print("🎉 All steps have been evaluated!", file=sys.stderr)
        # Save final results
        out_obj = {
            'model': args.model,
            'results': [],
            'summary': {}
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(out_obj, f, indent=2, ensure_ascii=False)
        return
    print(f"🚀 Steps to evaluate in this run: {total_steps}")

    # 2. Initialize statistics variables
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
    difficult_sub = {
        7: {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        8: {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        9: {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        10: {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        11: {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
        12: {'count': 0, 'feedback_matches': 0, 'config_correct': 0},
    }
    difficult_total = {'count': 0, 'feedback_matches': 0, 'config_correct': 0}

    results = []
    stats_lock = threading.Lock()  # Protect both statistics and checkpoint writing
    pbar = tqdm(total=total_steps, desc='Evaluating steps', unit='step')

    # 3. Concurrent task function (New: record completed tasks + save checkpoint)
    def process_single_task(task):
        s_idx, step_idx, step = task
        eval_result = evaluate_sample(step, args.model, args.temperature, openai_client, thinking=args.thinking)
        result_item = {
            'sample_index': s_idx,
            'step_index': step_idx,
            'change_count': step.get('change_count'),
            'result': eval_result
        }

        fb_ok = 1 if isinstance(eval_result, dict) and eval_result.get('feedback_match') else 0
        cfg_ok = 1 if isinstance(eval_result, dict) and eval_result.get('config_change_correct') else 0
        change_count_val = step.get('change_count')
        try:
            cc_val = int(change_count_val) if change_count_val is not None else -1
        except:
            cc_val = -1

        with stats_lock:
            results.append(result_item)
            # Overall statistics
            overall_total['count'] += 1
            overall_total['feedback_matches'] += fb_ok
            overall_total['config_correct'] += cfg_ok
            # Category statistics
            cat = classify_step(step)
            if cat and cat in categories:
                categories[cat]['count'] += 1
                categories[cat]['feedback_matches'] += fb_ok
                categories[cat]['config_correct'] += cfg_ok
                # Main category statistics
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
            # ====================== Record completed task + save checkpoint (New) ======================
            completed_tasks.add((s_idx, step_idx))
            save_checkpoint(args.checkpoint, completed_tasks)
            # ==========================================================================
        pbar.update(1)

    # 4. Execute concurrent evaluation
    try:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = [executor.submit(process_single_task, task) for task in tasks]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"\nTask failed with error: {str(e)}", file=sys.stderr)
    finally:
        pbar.close()
        # Final checkpoint save
        save_checkpoint(args.checkpoint, completed_tasks)

    # 5. Calculate percentages
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


    out_obj = {
        'model': args.model,
        'results': results,
        'summary': {
            'first_category': {'subcategories': {'success_false': categories['first_success_false'],'change0_args0': categories['first_change0_args0'],'change0_args1': categories['first_change0_args1']}, 'total': first_total},
            'second_category': {'subcategories': {'simple_1': categories['second_simple_1'],'simple_2': categories['second_simple_2'],'medium_3': categories['second_medium_3'],'medium_4': categories['second_medium_4'],'medium_5': categories['second_medium_5'],'medium_6': categories['second_medium_6'],'difficult_7_12': categories['second_difficult_7_12']}, 'total': second_total},
            'overall': overall_total,
            'custom_summary': {
                'simple_total': simple_total,
                'medium_total': medium_total,
                'difficult_sub': difficult_sub,
                'difficult_total': difficult_total
            }
        }
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(out_obj, f, indent=2, ensure_ascii=False)

    # Console output
    print(f"\nModel evaluated: {args.model}")
    print(f"Concurrent workers: {args.max_workers}")
    print(f"Output saved to: {args.output}")
    print(f"Checkpoint saved to: {args.checkpoint}")

    # First Category
    print("\n=== First Category (success false & change0) ===")
    print("  Subcategories:")
    for name, data in [('success_false', categories['first_success_false']),('change0_args0', categories['first_change0_args0']),('change0_args1', categories['first_change0_args1'])]:
        if data['count']:
            print(f"    {name}: count={data['count']}, feedback={data['feedback_matches']}/{data['count']} ({data['feedback_match_pct']:.2f}%), config={data['config_correct']}/{data['count']} ({data['config_correct_pct']:.2f}%)")
        else:
            print(f"    {name}: count=0")
    if first_total['count']:
        print(f"  Total: count={first_total['count']}, feedback={first_total['feedback_matches']}/{first_total['count']} ({first_total['feedback_match_pct']:.2f}%), config={first_total['config_correct']}/{first_total['count']} ({first_total['config_correct_pct']:.2f}%)")
    else:
        print("  No samples in First Category.")

    # Second Category
    print("\n=== Second Category (config_change 1-12) ===")
    print("  [Simple Group]")
    for name, data in [('simple_1', categories['second_simple_1']),('simple_2', categories['second_simple_2'])]:
        if data['count']:
            print(f"    {name}: count={data['count']}, feedback={data['feedback_matches']}/{data['count']} ({data['feedback_match_pct']:.2f}%), config={data['config_correct']}/{data['count']} ({data['config_correct_pct']:.2f}%)")
        else:
            print(f"    {name}: count=0")
    if simple_total['count']:
        print(f"  📊 Total Simple: count={simple_total['count']}, feedback={simple_total['feedback_matches']}/{simple_total['count']} ({simple_total['feedback_match_pct']:.2f}%), config={simple_total['config_correct']}/{simple_total['count']} ({simple_total['config_correct_pct']:.2f}%)")
    else:
        print("  No samples in Simple Group.")

    print("\n  [Medium Group]")
    for name, data in [('medium_3', categories['second_medium_3']),('medium_4', categories['second_medium_4']),('medium_5', categories['second_medium_5']),('medium_6', categories['second_medium_6'])]:
        if data['count']:
            print(f"    {name}: count={data['count']}, feedback={data['feedback_matches']}/{data['count']} ({data['feedback_match_pct']:.2f}%), config={data['config_correct']}/{data['count']} ({data['config_correct_pct']:.2f}%)")
        else:
            print(f"    {name}: count=0")
    if medium_total['count']:
        print(f"  📊 Total Medium: count={medium_total['count']}, feedback={medium_total['feedback_matches']}/{medium_total['count']} ({medium_total['feedback_match_pct']:.2f}%), config={medium_total['config_correct']}/{medium_total['count']} ({medium_total['config_correct_pct']:.2f}%)")
    else:
        print("  No samples in Medium Group.")

    print("\n  [Difficult Group (7-12)]")
    for cc_num in [7,8,9,10,11,12]:
        data = difficult_sub[cc_num]
        if data['count']:
            print(f"    difficult_{cc_num}: count={data['count']}, feedback={data['feedback_matches']}/{data['count']} ({data['feedback_match_pct']:.2f}%), config={data['config_correct']}/{data['count']} ({data['config_correct_pct']:.2f}%)")
        else:
            print(f"    difficult_{cc_num}: count=0")
    if difficult_total['count']:
        print(f"  📊 Total Difficult: count={difficult_total['count']}, feedback={difficult_total['feedback_matches']}/{difficult_total['count']} ({difficult_total['feedback_match_pct']:.2f}%), config={difficult_total['config_correct']}/{difficult_total['count']} ({difficult_total['config_correct_pct']:.2f}%)")
    else:
        print("  No samples in Difficult Group.")

    # Second Category Total
    if second_total['count']:
        print(f"\n  Total Second Category: count={second_total['count']}, feedback={second_total['feedback_matches']}/{second_total['count']} ({second_total['feedback_match_pct']:.2f}%), config={second_total['config_correct']}/{second_total['count']} ({second_total['config_correct_pct']:.2f}%)")
    else:
        print("\n  No samples in Second Category.")

    # Overall Statistics
    print("\n=== Overall (both categories) ===")
    if overall_total['count']:
        print(f"  count={overall_total['count']}, feedback={overall_total['feedback_matches']}/{overall_total['count']} ({overall_total['feedback_match_pct']:.2f}%), config={overall_total['config_correct']}/{overall_total['count']} ({overall_total['config_correct_pct']:.2f}%)")
    else:
        print("  No samples evaluated.")

    # Completion prompt
    print(f"\n🎉 Evaluation fully completed! Checkpoint saved. Delete this file to re-evaluate: {args.checkpoint}")


if __name__ == '__main__':
    main()
