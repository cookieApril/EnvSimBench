#!/usr/bin/env python3
"""
Usage:
  python3 sample_datasets.py \
    --false_in final_false_samples_fine.json \
    --true_in final_true_samples.json \
    --out combined_sample.json \
    --seed 42
"""
import argparse
import json
import random
import os
import re
from collections import defaultdict

# ===================== Reuse core functions of evaluation script (ensure consistent success judgment) =====================
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

def get_success_from_observation(sample):
    """【Core】Consistent success extraction logic with evaluation script"""
    obs = None
    # Prioritize getting observation from step_detail
    if 'step_detail' in sample and isinstance(sample['step_detail'], dict):
        obs = sample['step_detail'].get('observation')
    else:
        obs = sample.get('observation')
        
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
# ========================================================================================

def load_input(path):
    """Load JSON file (supports standard JSON array or line-delimited JSON)"""
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    try:
        data = json.loads(text)
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
            except Exception as e:
                print(f"Warning: Skip invalid JSON line {ln[:50]}... Error: {str(e)}")
                continue
        return items
    return []

def extract_args_count(action):
    """Extract number of arguments in action (align with args_count in logs)"""
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

def extract_item(sample, idx=None):
    """Extract metadata for sampling (fix env_id + add args_count + strictly extract success)"""
    item = {'orig': sample, 'orig_index': idx}
    
    # 1. Fix env_id extraction
    env_id = sample.get('env_code')
    if not env_id:
        env_id = sample.get('env_id') or sample.get('env') or sample.get('environment')
    sd = sample.get('step_detail')
    if sd and isinstance(sd, dict):
        env_id = env_id or sd.get('env_code') or sd.get('env_id') or sd.get('env')
    item['env_id'] = env_id or None

    # 2. Extract observation_content
    obs = None
    if sd and isinstance(sd, dict):
        ob = sd.get('observation')
        if isinstance(ob, dict):
            obs = ob.get('content')
        else:
            obs = ob
    else:
        ob = sample.get('observation')
        if isinstance(ob, dict):
            obs = ob.get('content')
        else:
            obs = ob
    item['observation_content'] = obs or ''

    # 3. Extract change_count
    change_count = None
    if sample.get('change_count') is not None:
        change_count = sample['change_count']
    elif sd and isinstance(sd, dict):
        config_change = sd.get('config_change')
        if config_change and isinstance(config_change, dict):
            change_count = config_change.get('change_count')
    try:
        if change_count is not None:
            change_count = int(change_count)
    except (ValueError, TypeError):
        change_count = None
    item['change_count'] = change_count

    # 4. Extract args_count
    args_count = 0
    if sd and isinstance(sd, dict):
        action = sd.get('action')
        args_count = extract_args_count(action)
    item['args_count'] = args_count

    # 5. Strictly extract success (fully consistent with evaluation script)
    item['success'] = get_success_from_observation(sample)

    # Debug log
    if idx is not None and idx < 10:
        print(f"Debug: Sample {idx} → env_id={item['env_id']}, change_count={item['change_count']}, args_count={item['args_count']}, success={item['success']}")
    
    return item

def pick_max_coverage(candidates, target, used_envs=None):
    """Prioritize unused env_id to maximize environment coverage"""
    used_envs = used_envs or set()
    selected = []
    if not candidates or target <= 0:
        return selected, used_envs

    by_env = defaultdict(list)
    for it in candidates:
        env = it.get('env_id') or 'unknown'
        by_env[env].append(it)

    unused_envs = [env for env in by_env.keys() if env not in used_envs]
    random.shuffle(unused_envs)
    for env in unused_envs:
        if len(selected) >= target:
            break
        env_items = by_env[env]
        random.shuffle(env_items)
        pick = env_items.pop()
        selected.append(pick)
        used_envs.add(env)
        if env_items:
            by_env[env] = env_items
        else:
            del by_env[env]

    remaining = []
    for env_items in by_env.values():
        remaining.extend(env_items)
    random.shuffle(remaining)
    for it in remaining:
        if len(selected) >= target:
            break
        if it not in selected:
            selected.append(it)
            used_envs.add(it.get('env_id') or 'unknown')

    return selected[:target], used_envs

def sample_false_20(false_items):
    """Category 1: Sample 20 false samples with success=False"""
    # 【Strict Constraint】Only keep samples with success=False
    valid_false = [it for it in false_items if it.get('success') is False]
    print(f"📥 Valid false samples (success=False): {len(valid_false)} items")
    
    target = 20
    selected, used_envs = pick_max_coverage(valid_false, target)
    print(f"✅ Category 1 - false_20: Sampled {len(selected)} items")
    return selected, used_envs

def sample_true_0_subset(true_items):
    """Category 1: Sample true samples with change_count=0 (40 for args_count=0/1 each) from success=True samples"""
    # 【Strict Constraint】Only keep samples with success=True
    valid_true = [it for it in true_items if it.get('success') is True]
    true_0_items = [it for it in valid_true if it.get('change_count') == 0]
    print(f"📥 Valid true samples (success=True): {len(valid_true)} items")
    print(f"📥 Total samples with change_count==0 in true file: {len(true_0_items)}")
  
    true_0_args_0 = [it for it in true_0_items if it.get('args_count') == 0]
    true_0_args_1 = [it for it in true_0_items if it.get('args_count') == 1]
    
    target_0 = 40
    target_1 = 40
    sel_0, used_envs_0 = pick_max_coverage(true_0_args_0, target_0)
    sel_1, used_envs_1 = pick_max_coverage(true_0_args_1, target_1, used_envs_0)
    
    print(f"✅ Category 1 - true_0_args_0: Sampled {len(sel_0)} items")
    print(f"✅ Category 1 - true_0_args_1: Sampled {len(sel_1)} items")
     
    return sel_0 + sel_1, used_envs_1

def sample_true_change_count_buckets(true_items, used_envs):
    """
    Category 2: Sample by change_count buckets (only keep valid samples with success=True)
    Core Modification: count=1(25) + count=2(25), 50 for others
    """
    # 【Strict Constraint】Only keep samples with success=True
    valid_true = [it for it in true_items if it.get('success') is True]
    true_non_0 = [it for it in valid_true if it.get('change_count', 0) > 0]
    
    # Split 1-2 into independent buckets, 25 items each
    buckets = {
        'simple_1':  [it for it in true_non_0 if it.get('change_count', 0) == 1],   
        'simple_2':  [it for it in true_non_0 if it.get('change_count', 0) == 2],   
        'medium_3':  [it for it in true_non_0 if it.get('change_count', 0) == 3],     
        'medium_4':  [it for it in true_non_0 if it.get('change_count', 0) == 4],    
        'medium_5':  [it for it in true_non_0 if it.get('change_count', 0) == 5],     
        'medium_6':  [it for it in true_non_0 if it.get('change_count', 0) == 6],    
        'difficult': [it for it in true_non_0 if 7 <= it.get('change_count', 0) <= 12] 
    }
    
    # Key Modification: Specify sampling quantity for each bucket
    bucket_targets = {
        'simple_1': 25,
        'simple_2': 25,
        'medium_3': 50,
        'medium_4': 50,
        'medium_5': 50,
        'medium_6': 50,
        'difficult': 50
    }

    selected = []
    for bucket_name, items in buckets.items():
        target = bucket_targets[bucket_name]
        sel, used_envs = pick_max_coverage(items, target, used_envs)
        selected.extend(sel)
        # Print log
        label = bucket_name.replace('simple_','count=') if 'simple' in bucket_name else bucket_name
        print(f"✅ Category 2 - {bucket_name} ({label}): Sampled {len(sel)} items")
    
    return selected, used_envs

def write_combined_output(selected, out_path, category_stats):
    """Write combined samples and print statistics"""
    arr = [it['orig'] for it in selected]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(arr, f, indent=2, ensure_ascii=False)
    
    env_ids = set(it.get('env_id') for it in selected if it.get('env_id') is not None)
    total_env = len(env_ids) if env_ids else 0
    
    print(f"\n📤 Finally wrote {len(arr)} samples to {out_path}")
    print(f"📊 Category quantity statistics:")
    for cat, count in category_stats.items():
        print(f"   {cat}：{count} items")
    print(f"🌐 Total covered env_id count: {total_env}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--false_in', default='/EnvScaler/result/7.false_samples_delete_error.json')
    parser.add_argument('--true_in', default='/EnvScaler/result/7.true_samples_delete_error.json')
    parser.add_argument('--out', default='/EnvScaler/result/9.choice_final_combined.json')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    cwd = os.path.dirname(os.path.abspath(__file__))
    false_path = args.false_in if os.path.isabs(args.false_in) else os.path.join(cwd, args.false_in)
    true_path = args.true_in if os.path.isabs(args.true_in) else os.path.join(cwd, args.true_in)

    # Load data
    false_data = load_input(false_path)
    true_data = load_input(true_path)
    print(f"📥 Load raw data: {len(false_data)} false samples, {len(true_data)} true samples")

    # Extract metadata (including success field)
    false_items = [extract_item(s, idx=i) for i, s in enumerate(false_data)]
    true_items = [extract_item(s, idx=i) for i, s in enumerate(true_data)]

    used_envs = set()
    all_selected = []
    category_stats = {}

    # 1. Sample false_20 with success=False
    sel_false_20, used_envs = sample_false_20(false_items)
    all_selected.extend(sel_false_20)
    category_stats['category1_false_20'] = len(sel_false_20)

    # 2. Sample true_0_args_0/1 with success=True
    sel_true_0, used_envs = sample_true_0_subset(true_items)
    all_selected.extend(sel_true_0)
    category_stats['category1_true_0_args_0'] = len([it for it in sel_true_0 if it.get('args_count') == 0])
    category_stats['category1_true_0_args_1'] = len([it for it in sel_true_0 if it.get('args_count') == 1])

    # 3. Sample change_count buckets with success=True
    sel_true_buckets, used_envs = sample_true_change_count_buckets(true_items, used_envs)
    all_selected.extend(sel_true_buckets)
    
    # 🔥 Count modified categories
    bucket_names = ['simple_1', 'simple_2', 'medium_3', 'medium_4', 'medium_5', 'medium_6', 'difficult']
    for bn in bucket_names:
        count = len([it for it in sel_true_buckets if 
                    (bn == 'simple_1' and it.get('change_count',0)==1) or
                    (bn == 'simple_2' and it.get('change_count',0)==2) or
                    (bn == 'medium_3' and it.get('change_count',0)==3) or
                    (bn == 'medium_4' and it.get('change_count',0)==4) or
                    (bn == 'medium_5' and it.get('change_count',0)==5) or
                    (bn == 'medium_6' and it.get('change_count',0)==6) or
                    (bn == 'difficult' and 7<=it.get('change_count',0)<=12)])
        category_stats[f'category2_{bn}'] = count

    # Write final file
    write_combined_output(all_selected, args.out, category_stats)

if __name__ == '__main__':
    main()
