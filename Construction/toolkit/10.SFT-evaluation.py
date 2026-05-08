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

# ====================== Checkpoint resume utility functions ======================
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
    """Save checkpoint file and write completed task list"""
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


# Try to import json_repair, set to None if not installed
try:
    from json_repair import repair_json
    REPAIR_AVAILABLE = True
except ImportError:
    REPAIR_AVAILABLE = False
    repair_json = None


def extract_first_json_block(text):
    """
    Extract the first complete JSON object using bracket counting.
    Solve repeated output problem like {...}{EIF{...}{EIF{...} from small models.
    Only return the first fully closed { ... } block, discard all subsequent repeated content.
    """
    depth = 0
    start = None
    in_string = False
    escape_next = False

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    candidate = text[start:i + 1]
                    # Try direct parsing
                    try:
                        return json.loads(candidate)
                    except Exception:
                        # Clean and parse
                        cleaned = re.sub(r',\s*}', '}', candidate)
                        cleaned = re.sub(r',\s*]', ']', cleaned)
                        try:
                            return json.loads(cleaned)
                        except Exception:
                            pass
                    # Reset to find next block
                    start = None
    return None


def extract_json(text):
    """
    Extract JSON object from LLM response, handle irregular outputs.
    Repair priority (high to low):
    1. Remove  tags (including unclosed ones)
    2. Truncate at known repeated separators
    3. Extract content from markdown code block
    4. Core upgrade: Bracket counting to get first valid JSON block
    5. Use json_repair for auto repair (if available)
    6. Fallback to standard json / ast.literal_eval
    """
    if not isinstance(text, str):
        return None

    # ---------- Step 1: Clean  tags ----------
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<think>[\s\S]*$', '', text, flags=re.IGNORECASE)

    # ---------- Step 2: Truncate known repeated separators ----------
    # Common repeated messy separators from small models
    REPEAT_SEPARATORS = [
        r'\tNdrFc',      
        r'\{EIF\{',      
        r'EIF\{',
    ]
    for sep_pattern in REPEAT_SEPARATORS:
        m = re.search(sep_pattern, text)
        if m:
            text = text[:m.start()]
            break

    # ---------- Step 3: Prioritize markdown code block ----------
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    m = re.search(code_block_pattern, text, flags=re.IGNORECASE)
    if m:
        block_text = m.group(1).strip()
        # Try bracket counting on block content first
        result = extract_first_json_block(block_text)
        if result is not None:
            return result
        try:
            return json.loads(block_text)
        except Exception:
            pass

    # ---------- Step 4: Bracket counting for first valid JSON ----------
    result = extract_first_json_block(text)
    if result is not None:
        return result

    # ---------- Step 5: Use json_repair to fix and parse ----------
    if REPAIR_AVAILABLE:
        try:
            repaired = repair_json(text, return_objects=True)
            if isinstance(repaired, dict):
                return repaired
            if isinstance(repaired, list) and len(repaired) == 1 and isinstance(repaired[0], dict):
                return repaired[0]
            return None
        except Exception:
            pass

    # ---------- Step 6: Fallback solution ----------
    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        import ast
        return ast.literal_eval(text)
    except Exception:
        pass

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

    system_prompt = (
        f"Environment code:\n\n{env_code}\n\n"
        f"Initial config:\n{json.dumps(cfg_before, ensure_ascii=False, indent=2)}\n\n"
        f"Instructions: You are given the environment code and the initial config. "
        f"A tool call will be provided; you must predict the environment's textual feedback "
        f"(exact output string) and any configuration changes that result from executing the tool. "
        f"Only report config changes using types: add, modify, delete. "
        f"Output ONLY a JSON object with keys: "
        f"\"feedback\": string, \"config_changes\": [{{\"type\":..., \"path\":..., \"value\": ...}}]. "
        f"If no config change, set \"config_changes\": []. "
        f"Do not output other text. Do not repeat the JSON. Output exactly one JSON object and stop."
    )

    user_prompt = f"Tool call: {call_str}\n\nReturn the JSON as specified."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    extra_body = {
        "repetition_penalty": 1.15,
        "stop": ["\n\n\n\n", "}{", "{EIF", "NdrFc"],
    }

    resp_text = None
    for attempt in range(max_retries + 1):
        try:
            resp = openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=4096,      
                timeout=300.0,
                extra_body=extra_body,  
            )
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
        except Exception:
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
    p.add_argument('--input', default='./eval/9.choice_final_combined-167env.json')
    p.add_argument('-o', '--output', default=None, help='Output JSON file')
    p.add_argument('--model', default='gemini-3.1-pro-preview')
    p.add_argument('--temperature', type=float, default=0.0)
    p.add_argument('--max_samples', type=int, default=400)
    p.add_argument('--max_workers', type=int, default=5)
    p.add_argument('--thinking', type=bool, default=False)
    p.add_argument('--checkpoint', default=None, help='Checkpoint file path for resuming evaluation')
    args = p.parse_args()

    if openai is None:
        print('openai package not available; pip install openai')
        return
    if 'OPENAI_API_KEY' not in os.environ:
        print('Please set OPENAI_API_KEY in environment')
        return

    base_url = os.environ.get('OPENAI_BASE_URL', 'http://localhost:8000/v1')
    api_key = os.environ.get('OPENAI_API_KEY', 'dummy')
    openai_client = openai.OpenAI(
        base_url=base_url,
        api_key=api_key,
    )
    print(f"✅ OpenAI client initialized, base_url={base_url}")

    if args.output is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_model = args.model.replace('/', '_')
        args.output = f'./eval/result/{safe_model}_qwen3_4b_base_new_eval_results_{timestamp}.json'

    if args.checkpoint is None:
        base_dir = os.path.dirname(args.output)
        os.makedirs(base_dir, exist_ok=True)
        args.checkpoint = os.path.join(base_dir, "eval_checkpoint_qwen3_4b_base_new.json")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    completed_tasks = load_checkpoint(args.checkpoint)
    print(f"✅ Checkpoint loaded: {len(completed_tasks)} evaluation steps already completed")

    samples = []
    try:
        items = load_input(args.input)
        for it in items:
            if isinstance(it, dict):
                samples.append(it)
    except Exception as e:
        print(f'Error loading input {args.input}: {e}', file=sys.stderr)
        return

    tasks = []
    task_count = 0
    for s_idx, sample in enumerate(samples):
        steps = extract_steps(sample)
        for step_idx, step in enumerate(steps):
            if args.max_samples and task_count >= args.max_samples:
                break
            if (s_idx, step_idx) in completed_tasks:
                continue
            tasks.append((s_idx, step_idx, step))
            task_count += 1

    total_steps = len(tasks)
    if total_steps == 0:
        print("🎉 All evaluation steps are already completed!", file=sys.stderr)
        out_obj = {
            'model': args.model,
            'results': [],
            'summary': {}
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(out_obj, f, indent=2, ensure_ascii=False)
        return
    print(f"🚀 Steps to evaluate in this run: {total_steps}")

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
    stats_lock = threading.Lock()
    pbar = tqdm(total=total_steps, desc='Evaluating steps', unit='step')

    def process_single_task(task):
        s_idx, step_idx, step = task
        eval_result = evaluate_sample(
            step, args.model, args.temperature, openai_client, thinking=args.thinking
        )
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
        except Exception:
            cc_val = -1

        with stats_lock:
            results.append(result_item)
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
            completed_tasks.add((s_idx, step_idx))
            save_checkpoint(args.checkpoint, completed_tasks)
        pbar.update(1)

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
        save_checkpoint(args.checkpoint, completed_tasks)

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
            'first_category': {
                'subcategories': {
                    'success_false': categories['first_success_false'],
                    'change0_args0': categories['first_change0_args0'],
                    'change0_args1': categories['first_change0_args1'],
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
                    'difficult_7_12': categories['second_difficult_7_12'],
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
    }

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(out_obj, f, indent=2, ensure_ascii=False)

    print(f"\nModel evaluated: {args.model}")
    print(f"Concurrent workers: {args.max_workers}")
    print(f"Output saved to: {args.output}")
    print(f"Checkpoint saved to: {args.checkpoint}")

    print("\n=== First Category (success false & change0) ===")
    print("  Subcategories:")
    for name, data in [
        ('success_false', categories['first_success_false']),
        ('change0_args0', categories['first_change0_args0']),
        ('change0_args1', categories['first_change0_args1']),
    ]:
        if data['count']:
            print(f"    {name}: count={data['count']}, feedback={data['feedback_matches']}/{data['count']} "
                  f"({data['feedback_match_pct']:.2f}%), config={data['config_correct']}/{data['count']} "
                  f"({data['config_correct_pct']:.2f}%)")
        else:
            print(f"    {name}: count=0")
    if first_total['count']:
        print(f"  Total: count={first_total['count']}, "
              f"feedback={first_total['feedback_matches']}/{first_total['count']} "
              f"({first_total['feedback_match_pct']:.2f}%), "
              f"config={first_total['config_correct']}/{first_total['count']} "
              f"({first_total['config_correct_pct']:.2f}%)")
    else:
        print("  No samples in First Category.")

    print("\n=== Second Category (config_change 1-12) ===")
    print("  [Simple Group]")
    for name, data in [
        ('simple_1', categories['second_simple_1']),
        ('simple_2', categories['second_simple_2']),
    ]:
        if data['count']:
            print(f"    {name}: count={data['count']}, feedback={data['feedback_matches']}/{data['count']} "
                  f"({data['feedback_match_pct']:.2f}%), config={data['config_correct']}/{data['count']} "
                  f"({data['config_correct_pct']:.2f}%)")
        else:
            print(f"    {name}: count=0")
    if simple_total['count']:
        print(f"  📊 Total Simple: count={simple_total['count']}, "
              f"feedback={simple_total['feedback_matches']}/{simple_total['count']} "
              f"({simple_total['feedback_match_pct']:.2f}%), "
              f"config={simple_total['config_correct']}/{simple_total['count']} "
              f"({simple_total['config_correct_pct']:.2f}%)")
    else:
        print("  No samples in Simple Group.")

    print("\n  [Medium Group]")
    for name, data in [
        ('medium_3', categories['second_medium_3']),
        ('medium_4', categories['second_medium_4']),
        ('medium_5', categories['second_medium_5']),
        ('medium_6', categories['second_medium_6']),
    ]:
        if data['count']:
            print(f"    {name}: count={data['count']}, feedback={data['feedback_matches']}/{data['count']} "
                  f"({data['feedback_match_pct']:.2f}%), config={data['config_correct']}/{data['count']} "
                  f"({data['config_correct_pct']:.2f}%)")
        else:
            print(f"    {name}: count=0")
    if medium_total['count']:
        print(f"  📊 Total Medium: count={medium_total['count']}, "
              f"feedback={medium_total['feedback_matches']}/{medium_total['count']} "
              f"({medium_total['feedback_match_pct']:.2f}%), "
              f"config={medium_total['config_correct']}/{medium_total['count']} "
              f"({medium_total['config_correct_pct']:.2f}%)")
    else:
        print("  No samples in Medium Group.")

    print("\n  [Difficult Group (7-12)]")
    for cc_num in [7, 8, 9, 10, 11, 12]:
        data = difficult_sub[cc_num]
        if data['count']:
            print(f"    difficult_{cc_num}: count={data['count']}, "
                  f"feedback={data['feedback_matches']}/{data['count']} "
                  f"({data['feedback_match_pct']:.2f}%), "
                  f"config={data['config_correct']}/{data['count']} "
                  f"({data['config_correct_pct']:.2f}%)")
        else:
            print(f"    difficult_{cc_num}: count=0")
    if difficult_total['count']:
        print(f"  📊 Total Difficult: count={difficult_total['count']}, "
              f"feedback={difficult_total['feedback_matches']}/{difficult_total['count']} "
              f"({difficult_total['feedback_match_pct']:.2f}%), "
              f"config={difficult_total['config_correct']}/{difficult_total['count']} "
              f"({difficult_total['config_correct_pct']:.2f}%)")
    else:
        print("  No samples in Difficult Group.")

    if second_total['count']:
        print(f"\n  Total Second Category: count={second_total['count']}, "
              f"feedback={second_total['feedback_matches']}/{second_total['count']} "
              f"({second_total['feedback_match_pct']:.2f}%), "
              f"config={second_total['config_correct']}/{second_total['count']} "
              f"({second_total['config_correct_pct']:.2f}%)")
    else:
        print("\n  No samples in Second Category.")

    print("\n=== Overall (both categories) ===")
    if overall_total['count']:
        print(f"  count={overall_total['count']}, "
              f"feedback={overall_total['feedback_matches']}/{overall_total['count']} "
              f"({overall_total['feedback_match_pct']:.2f}%), "
              f"config={overall_total['config_correct']}/{overall_total['count']} "
              f"({overall_total['config_correct_pct']:.2f}%)")
    else:
        print("  No samples evaluated.")

    print(f"\n🎉 Evaluation completed! Checkpoint saved. Delete the file to re-run evaluation: {args.checkpoint}")


if __name__ == '__main__':
    main()
