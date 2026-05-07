import json
import re
from pathlib import Path

# ===================== 路径配置 =====================
INPUT_PATH = "/data/EnvScaler/interact_with_env/result/12.select-SFT-data-noreasoning-selectedByTaskid-Change-balance2.json"
OUTPUT_PATH = "/data/EnvScaler/interact_with_env/result/13.SFT-data-noreasoning-selectedByTaskid-Change-balance2.json"

# ================ 核心工具函数 ================
def action_to_call(action):
    """将 action 转换为工具调用字符串"""
    if not isinstance(action, dict):
        return str(action)
    name = action.get('name') or action.get('action') or 'call'
    args = action.get('arguments') or action.get('args') or {}
    try:
        arg_str = json.dumps(args, ensure_ascii=False)
    except Exception:
        arg_str = str(args)
    return f"{name}({arg_str})"

def diff_dicts(before, after, prefix=""):
    """递归对比字典，生成配置变更列表"""
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
            elif b != a:
                changes.append({"path": path, "type": "modified", "before": b, "after": a})
    return changes

def normalize_text(value):
    """清理非法转义字符，确保JSON可解析"""
    if value is None:
        return ""
    if isinstance(value, str):
        # 仅保留合法转义：\n \t \r \"，其余反斜杠转义
        value = re.sub(r'\\(?!n|t|r|")', r"\\\\", value)
        value = value.replace("\x00", "")  # 移除空字符
        value = value.replace("\r", "")    # 移除回车符
        return value
    try:
        # 标准序列化，无兼容参数
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return normalize_text(str(value))

def clean_json_string(json_str):
    """修复JSON格式：移除多余逗号、首尾空格"""
    json_str = json_str.strip()
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    return json_str

# ===================== 数据转换主逻辑 =====================
with open(INPUT_PATH, 'r', encoding='utf-8') as f:
    your_data = json.load(f)

alpaca_data = []

for sample_idx, sample in enumerate(your_data):
    try:
        # 1. 读取核心字段
        task_full = normalize_text(sample["task_info"]["task"]).strip()
        real_env_code = normalize_text(sample.get("env_code", ""))
        step_detail = sample.get("step_detail", {})
        
        # 2. 提取配置、动作、观测
        config_before = step_detail.get("config_before", {})
        config_after = step_detail.get("config_after", {})
        action = step_detail.get("action", {})
        observation = step_detail.get("observation", {})
        
        # 3. 生成标准字段
        tool_call = action_to_call(action)
        real_changes = diff_dicts(config_before, config_after)
        obs_content = observation.get("content", "") if isinstance(observation, dict) else normalize_text(observation)

        # 4. 构造指令
        instruction = f"""You are simulating a task execution environment. Given the environment code, initial configuration, and tool call, return the exact environment feedback and configuration changes.

Environment Code:
{real_env_code}

Execute the tool call strictly and output the standard result."""

        # 5. 构造输入输出（无兼容参数）
        input_text = json.dumps({
            "initial_config": config_before,
            "tool_call": tool_call
        }, ensure_ascii=False, indent=2)
        input_text = normalize_text(input_text)

        output_text = json.dumps({
            "feedback": obs_content,
            "config_changes": real_changes
        }, ensure_ascii=False, indent=2)
        output_text = normalize_text(output_text)

        # 6. 加入数据集
        alpaca_data.append({
            "instruction": instruction,
            "input": input_text,
            "output": output_text
        })
        
    except Exception as e:
        print(f"⚠️ 处理样本 {sample_idx} 时出错：{str(e)[:100]}，跳过该样本")
        continue

# 保存为合法 JSONL 格式
output_path = Path(OUTPUT_PATH)
output_path.parent.mkdir(parents=True, exist_ok=True)

with open(output_path, "w", encoding="utf-8", newline="\n") as f:
    for record in alpaca_data:
        try:
            json_str = json.dumps(record, ensure_ascii=False, allow_nan=False)
            json_str = clean_json_string(json_str)
            f.write(json_str + "\n")
        except:
            continue

print(f"✅ 转换完成！共生成 {len(alpaca_data)} 条有效训练样本")
print(f"✅ 数据集已保存至：{OUTPUT_PATH}")