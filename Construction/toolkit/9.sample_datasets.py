#!/usr/bin/env python3
"""
Sample datasets from final_false_samples_fine.json and final_true_samples.json
修复 env_id 提取逻辑，拆分 simple 为 count=1(25条) + count=2(25条)，对齐 400 条样本采样规则
【严格约束】：false样本必须success=False，true样本必须success=True（与评估脚本逻辑完全一致）

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

# ===================== 复用评估脚本的核心函数（保证success判断完全一致） =====================
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
    """【核心】与评估脚本完全一致的success提取逻辑"""
    obs = None
    # 优先从step_detail取observation
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
    """加载JSON文件（支持普通JSON数组或行分隔JSON）"""
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except Exception:
        items = []
        for ln in text.splitlines():
            ln = ln.strip()  # 修复原脚本bug：缺少ln.
            if not ln:
                continue
            try:
                items.append(json.loads(ln))
            except Exception as e:
                print(f"警告：跳过无效JSON行 {ln[:50]}... 错误：{str(e)}")
                continue
        return items
    return []

def extract_args_count(action):
    """提取action中的参数数量（对齐用户日志中的args_count）"""
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
    """提取采样所需的元数据（修复env_id+补充args_count+严格提取success）"""
    item = {'orig': sample, 'orig_index': idx}
    
    # 1. 修复env_id提取
    env_id = sample.get('env_code')
    if not env_id:
        env_id = sample.get('env_id') or sample.get('env') or sample.get('environment')
    sd = sample.get('step_detail')
    if sd and isinstance(sd, dict):
        env_id = env_id or sd.get('env_code') or sd.get('env_id') or sd.get('env')
    item['env_id'] = env_id or None

    # 2. 提取observation_content
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

    # 3. 提取change_count
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

    # 4. 提取args_count
    args_count = 0
    if sd and isinstance(sd, dict):
        action = sd.get('action')
        args_count = extract_args_count(action)
    item['args_count'] = args_count

    # 5. 【核心新增】严格提取success（与评估脚本完全一致）
    item['success'] = get_success_from_observation(sample)

    # 调试日志
    if idx is not None and idx < 10:
        print(f"调试：样本{idx} → env_id={item['env_id']}, change_count={item['change_count']}, args_count={item['args_count']}, success={item['success']}")
    
    return item

def pick_max_coverage(candidates, target, used_envs=None):
    """优先选择未使用过的env_id，最大化环境覆盖"""
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
    """第一大类：抽取【success=False】的false样本20条"""
    # 【强约束】仅保留success=False的样本
    valid_false = [it for it in false_items if it.get('success') is False]
    print(f"📥 有效false样本(success=False)：{len(valid_false)} 条")
    
    target = 20
    selected, used_envs = pick_max_coverage(valid_false, target)
    print(f"✅ 第一大类 - false_20：抽取 {len(selected)} 条")
    return selected, used_envs

def sample_true_0_subset(true_items):
    """第一大类：抽取【success=True】的true样本中change_count=0的子集（args_count=0/1 各40）"""
    # 【强约束】仅保留success=True的样本
    valid_true = [it for it in true_items if it.get('success') is True]
    true_0_items = [it for it in valid_true if it.get('change_count') == 0]
    print(f"📥 有效true样本(success=True)：{len(valid_true)} 条")
    print(f"📥 true文件中change_count==0的样本总数：{len(true_0_items)}")
    
    true_0_args_0 = [it for it in true_0_items if it.get('args_count') == 0]
    true_0_args_1 = [it for it in true_0_items if it.get('args_count') == 1]
    
    target_0 = 40
    target_1 = 40
    sel_0, used_envs_0 = pick_max_coverage(true_0_args_0, target_0)
    sel_1, used_envs_1 = pick_max_coverage(true_0_args_1, target_1, used_envs_0)
    
    print(f"✅ 第一大类 - true_0_args_0：抽取 {len(sel_0)} 条")
    print(f"✅ 第一大类 - true_0_args_1：抽取 {len(sel_1)} 条")
    
    return sel_0 + sel_1, used_envs_1

def sample_true_change_count_buckets(true_items, used_envs):
    """
    第二大类：按change_count分桶抽取（仅保留success=True的有效样本）
    核心修改：count=1(25) + count=2(25)，其余各50
    """
    # 【强约束】仅保留success=True的样本
    valid_true = [it for it in true_items if it.get('success') is True]
    true_non_0 = [it for it in valid_true if it.get('change_count', 0) > 0]
    
    # 🔥 关键修改：拆分 1-2 为独立桶，各25条
    buckets = {
        'simple_1':  [it for it in true_non_0 if it.get('change_count', 0) == 1],   # count=1 → 25条
        'simple_2':  [it for it in true_non_0 if it.get('change_count', 0) == 2],   # count=2 → 25条
        'medium_3':  [it for it in true_non_0 if it.get('change_count', 0) == 3],     # 3 → 50
        'medium_4':  [it for it in true_non_0 if it.get('change_count', 0) == 4],     # 4 → 50
        'medium_5':  [it for it in true_non_0 if it.get('change_count', 0) == 5],     # 5 → 50
        'medium_6':  [it for it in true_non_0 if it.get('change_count', 0) == 6],     # 6 → 50
        'difficult': [it for it in true_non_0 if 7 <= it.get('change_count', 0) <= 12] #7-12→50
    }
    
    # 🔥 关键修改：指定每个桶的抽取数量
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
        # 打印日志
        label = bucket_name.replace('simple_','count=') if 'simple' in bucket_name else bucket_name
        print(f"✅ 第二大类 - {bucket_name} ({label})：抽取 {len(sel)} 条")
    
    return selected, used_envs

def write_combined_output(selected, out_path, category_stats):
    """写入合并后的样本，并打印统计信息"""
    arr = [it['orig'] for it in selected]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(arr, f, indent=2, ensure_ascii=False)
    
    env_ids = set(it.get('env_id') for it in selected if it.get('env_id') is not None)
    total_env = len(env_ids) if env_ids else 0
    
    print(f"\n📤 最终写入 {len(arr)} 条样本到 {out_path}")
    print(f"📊 各分类数量统计：")
    for cat, count in category_stats.items():
        print(f"   {cat}：{count} 条")
    print(f"🌐 总覆盖env_id数量：{total_env}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--false_in', default='/data/EnvScaler/interact_with_env/result/7.false_samples_delete_error.json')
    parser.add_argument('--true_in', default='/data/EnvScaler/interact_with_env/result/7.true_samples_delete_error.json')
    parser.add_argument('--out', default='/data/EnvScaler/interact_with_env/result/9.choice_final_combined.json')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    cwd = os.path.dirname(os.path.abspath(__file__))
    false_path = args.false_in if os.path.isabs(args.false_in) else os.path.join(cwd, args.false_in)
    true_path = args.true_in if os.path.isabs(args.true_in) else os.path.join(cwd, args.true_in)

    # 加载数据
    false_data = load_input(false_path)
    true_data = load_input(true_path)
    print(f"📥 加载原始数据：false样本{len(false_data)}条，true样本{len(true_data)}条")

    # 提取元数据（包含success字段）
    false_items = [extract_item(s, idx=i) for i, s in enumerate(false_data)]
    true_items = [extract_item(s, idx=i) for i, s in enumerate(true_data)]

    used_envs = set()
    all_selected = []
    category_stats = {}

    # 1. 采样【success=False】的false_20
    sel_false_20, used_envs = sample_false_20(false_items)
    all_selected.extend(sel_false_20)
    category_stats['category1_false_20'] = len(sel_false_20)

    # 2. 采样【success=True】的true_0_args_0/1
    sel_true_0, used_envs = sample_true_0_subset(true_items)
    all_selected.extend(sel_true_0)
    category_stats['category1_true_0_args_0'] = len([it for it in sel_true_0 if it.get('args_count') == 0])
    category_stats['category1_true_0_args_1'] = len([it for it in sel_true_0 if it.get('args_count') == 1])

    # 3. 采样【success=True】的change_count分桶
    sel_true_buckets, used_envs = sample_true_change_count_buckets(true_items, used_envs)
    all_selected.extend(sel_true_buckets)
    
    # 🔥 统计修改后的分类
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

    # 写入最终文件
    write_combined_output(all_selected, args.out, category_stats)

if __name__ == '__main__':
    main()