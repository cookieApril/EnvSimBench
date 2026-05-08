import json
import ast
import re
import os  
from openai import OpenAI  # 替换：
from pathlib import Path

# ===================== Configuration =====================
# Hardcode your API Key and Base URL here, no need to export environment variables
os.environ["OPENAI_API_KEY"] = "sk-123abc"
os.environ["OPENAI_BASE_URL"] = "https://123abc"
# ==========================================================

def extract_tool_name(tool_call: str) -> str:
    """Extract function name from tool_call string"""
    match = re.match(r"(\w+)\(", tool_call)
    return match.group(1) if match else ""


def extract_tool_code(env_code: str, tool_name: str) -> str:
    """Extract specified function code from environment code"""
    try:
        tree = ast.parse(env_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == tool_name:
                lines = env_code.splitlines()
                start = node.lineno - 1
                end = node.end_lineno
                return "\n".join(lines[start:end])
    except Exception:
        pass
    
    pattern = rf"(    def {tool_name}\(.*?)(?=\n    def |\Z)"
    match = re.search(pattern, env_code, re.DOTALL)
    return match.group(1) if match else env_code[:2000]


def extract_relevant_state(tool_name: str, full_config: dict) -> dict:
    """Heuristically extract relevant state based on function name to reduce token consumption"""
    
    STATE_MAP = {
        "user": ["users"],
        "session": ["sessions", "users"],
        "post": ["posts"],
        "comment": ["comments", "posts"],
        "subreddit": ["subreddits"],
        "task": ["tasks"],
        "project": ["projects", "tasks"],
        "station": ["stations"],
        "observation": ["observations", "stations"],
        "aqi": ["aqi_records", "stations", "observations"],
    }
    
    relevant_keys = set()
    tool_lower = tool_name.lower()
    
    for keyword, keys in STATE_MAP.items():
        if keyword in tool_lower:
            relevant_keys.update(keys)
    
    if not relevant_keys:
        relevant_keys = set(full_config.keys())
    
    result = {}
    for key in relevant_keys:
        if key in full_config:
            data = full_config[key]
            if isinstance(data, dict) and len(data) > 5:
                result[key] = dict(list(data.items())[:5])
            else:
                result[key] = data
    
    return result


def generate_reason(client: OpenAI, sample: dict) -> str:
    """Generate reasoning for a single SFT sample"""
    
    instruction = sample.get("instruction", "")
    input_data = sample.get("input", {})
    output_data = sample.get("output", {})
    
    if isinstance(input_data, str):
        try:
            input_data = json.loads(input_data)
        except:
            input_data = {}
    
    tool_call = input_data.get("tool_call", "")
    full_config = input_data.get("initial_config", {})
    
    if isinstance(output_data, str):
        try:
            output_data = json.loads(output_data)
        except:
            output_data = {"feedback": output_data, "config_changes": []}
    
    feedback = output_data.get("feedback", "")
    config_changes = output_data.get("config_changes", [])
    
    tool_name = extract_tool_name(tool_call)
    
    env_code_match = re.search(
        r"Environment Code:\n(.*?)(?=\n\nExecute|$)", 
        instruction, 
        re.DOTALL
    )
    env_code = env_code_match.group(1) if env_code_match else ""
    tool_code = extract_tool_code(env_code, tool_name) if env_code else ""
    
    relevant_state = extract_relevant_state(tool_name, full_config)
    
    prompt = f"""You are analyzing a tool execution step in a simulated environment.

Given the following information, generate a concise step-by-step execution trace that explains:
1. Which validation checks are performed and whether they pass or fail
2. Which state fields are read
3. Which state fields are modified (if any), and what the new values are
4. What the return value is and why

Keep the reasoning focused ONLY on code execution logic. Do NOT speculate beyond what the code does.
Output: a numbered list of short steps, maximum 8 steps, each step under 30 words.

=== TOOL IMPLEMENTATION ===
{tool_code if tool_code else "[Full environment code provided - function: " + tool_name + "]"}

=== RELEVANT STATE (before execution) ===
{json.dumps(relevant_state, ensure_ascii=False, indent=2)}

=== TOOL CALL ===
{tool_call}

=== EXECUTION RESULT ===
Feedback: {feedback}
Config changes: {json.dumps(config_changes, ensure_ascii=False)}

Generate the execution trace (numbered steps only, no preamble):"""

    # ===================== OpenAI API Call =====================
    response = client.chat.completions.create(
        model="gpt-4o",  
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )
    # ==========================================================
    
    return response.choices[0].message.content.strip()


def process_sft_file(
    input_path: str, 
    output_path: str,
    max_samples: int = None,
    skip_no_change: bool = False
):
    """Process SFT dataset file"""
    # Initialize OpenAI client (auto load env vars set in code)
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL")
    )
    
    input_file = Path(input_path)
    output_file = Path(output_path)
    
    processed_ids = set()
    if output_file.exists():
        with open(output_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    if obj.get("reason", "") != "":
                        processed_ids.add(obj.get("_id", ""))
                except:
                    pass
        print(f"Resumed: {len(processed_ids)} samples already completed, continuing remaining tasks...")
    
    with open(input_file, "r", encoding="utf-8") as fin, \
         open(output_file, "a", encoding="utf-8") as fout:
        
        count = 0
        skipped = 0
        
        for line_idx, line in enumerate(fin):
            line = line.strip()
            if not line:
                continue
            
            try:
                sample = json.loads(line)
            except json.JSONDecodeError:
                print(f"Skipping line {line_idx}: invalid JSON format")
                continue
            
            sample_id = f"line_{line_idx}"
            sample["_id"] = sample_id
            
            if sample_id in processed_ids:
                continue
            
            output_data = sample.get("output", {})
            if isinstance(output_data, str):
                try:
                    output_data = json.loads(output_data)
                except:
                    output_data = {}
            
            config_changes = output_data.get("config_changes", [])
            
            if skip_no_change and len(config_changes) == 0:
                skipped += 1
                sample["reason"] = ""
                fout.write(json.dumps(sample, ensure_ascii=False) + "\n")
                continue
            
            try:
                reason = generate_reason(client, sample)
                sample["reason"] = reason
                print(f"[{line_idx}] {extract_tool_name(sample.get('input', {}).get('tool_call', '') if isinstance(sample.get('input'), dict) else '')}: OK")
                
                fout.write(json.dumps(sample, ensure_ascii=False) + "\n")
                fout.flush()
                
            except Exception as e:
                print(f"[{line_idx}] Generation failed: {e}")
                print("API error occurred, program paused. Check quota/network and restart to resume.")
                break
            
            count += 1
            if max_samples and count >= max_samples:
                print(f"Reached max sample limit {max_samples}, stop processing")
                break
    
    print(f"Run completed: {count} generated, {skipped} skipped")


def rebuild_sft_with_reason(input_path: str, output_path: str):
    with open(input_path, "r", encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:
        
        for line in fin:
            line = line.strip()
            if not line:
                continue
            
            sample = json.loads(line)
            reason = sample.pop("reason", "")
            sample.pop("_id", None)
            
            output_data = sample.get("output", {})
            if isinstance(output_data, str):
                try:
                    output_data = json.loads(output_data)
                except:
                    pass
            
            if reason:
                sample["output"] = f"\n{reason}\n\n{json.dumps(output_data, ensure_ascii=False)}"
            
            fout.write(json.dumps(sample, ensure_ascii=False) + "\n")
    
    print(f"Rebuild finished, final dataset saved to {output_path}")


if __name__ == "__main__":
    # Modify file paths according to your needs
    process_sft_file(
        input_path="/EnvScaler/result/13.sft_data_alpaca_en-selectByTask.json",
        output_path="/EnvScaler/result/14.sft_data_with_reason_raw-selectByTask.jsonl",
        skip_no_change=True,
        max_samples=None
    )
    
    # Run rebuild ONLY after ALL samples are fully processed
    # Comment out this part if stopped halfway by API error
    # Uncomment after full completion to generate final dataset
    rebuild_sft_with_reason(
        input_path="/EnvScaler/result/14.sft_data_with_reason_raw-selectByTask.jsonl",
        output_path="/EnvScaler/result/14.sft_data_final.jsonl-selectByTask"
    )
