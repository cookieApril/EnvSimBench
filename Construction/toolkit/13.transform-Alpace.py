import json
import re
from pathlib import Path

# ===================== Path Configuration =====================
INPUT_PATH = "/EnvScaler/result/12.select-SFT-data-noreasoning.json"
OUTPUT_PATH = "/EnvScaler/result/13.sft_data_alpaca_en.json"

# ================ Core Utility Functions ================
def action_to_call(action):
    """Convert action to tool call string"""
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
    """Recursively compare dictionaries and generate configuration change list"""
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
    """Clean invalid escape characters to ensure JSON parsability"""
    if value is None:
        return ""
    if isinstance(value, str):
        # Only keep valid escapes: \n \t \r \", escape other backslashes
        value = re.sub(r'\\(?!n|t|r|")', r"\\\\", value)
        value = value.replace("\x00", "")  # Remove null characters
        value = value.replace("\r", "")    # Remove carriage returns
        return value
    try:
        # Standard serialization without compatibility parameters
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return normalize_text(str(value))

def clean_json_string(json_str):
    """Fix JSON format: remove redundant commas, leading and trailing spaces"""
    json_str = json_str.strip()
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    return json_str

# ===================== Main Data Conversion Logic =====================
with open(INPUT_PATH, 'r', encoding='utf-8') as f:
    your_data = json.load(f)

alpaca_data = []

for sample_idx, sample in enumerate(your_data):
    try:
        # 1. Read core fields
        task_full = normalize_text(sample["task_info"]["task"]).strip()
        real_env_code = normalize_text(sample.get("env_code", ""))
        step_detail = sample.get("step_detail", {})
        
        # 2. Extract configuration, action, observation
        config_before = step_detail.get("config_before", {})
        config_after = step_detail.get("config_after", {})
        action = step_detail.get("action", {})
        observation = step_detail.get("observation", {})
        
        # 3. Generate standard fields
        tool_call = action_to_call(action)
        real_changes = diff_dicts(config_before, config_after)
        obs_content = observation.get("content", "") if isinstance(observation, dict) else normalize_text(observation)

        # 4. Construct instruction
        instruction = f"""You are simulating a task execution environment. Given the environment code, initial configuration, and tool call, return the exact environment feedback and configuration changes.

Environment Code:
{real_env_code}

Execute the tool call strictly and output the standard result."""

        # 5. Construct input and output (no compatibility parameters)
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

        # 6. Add to dataset
        alpaca_data.append({
            "instruction": instruction,
            "input": input_text,
            "output": output_text
        })
        
    except Exception as e:
        print(f"⚠️ Error processing sample {sample_idx}: {str(e)[:100]}, skipping this sample")
        continue

# Save as valid JSONL format
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

print(f"✅ Conversion completed! Generated {len(alpaca_data)} valid training samples in total")
print(f"✅ Dataset saved to: {OUTPUT_PATH}")
