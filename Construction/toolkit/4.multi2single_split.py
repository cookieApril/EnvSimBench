import json
import os

def split_multi_round_to_single_round(input_file, output_file):
    """
    Split multi-round trajectory JSON file into single-round samples (retain all information of each step)
    :param input_file: Path to input JSON file (contains multi-round samples)
    :param output_file: Path to output JSON file (split single-round samples)
    """
    # 1. Read input file, support JSON or JSONL format
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        print(f"Error: Input file {input_file} does not exist")
        return

    # First try to parse the content as a complete JSON object
    multi_round_data = None
    try:
        multi_round_data = json.loads(text)
    except Exception:
        # Parse line by line as JSONL if standard JSON parsing fails
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        items = []
        for ln in lines:
            try:
                items.append(json.loads(ln))
            except Exception:
                # Ignore lines that fail to parse
                continue
        multi_round_data = items

    # 2. Initialize the list for single-round samples
    single_round_data = []

    # If the top-level data is a dictionary, identify the sample-containing structure
    if isinstance(multi_round_data, dict):
        if "trajectory" in multi_round_data:
            multi_round_data = [multi_round_data]
        else:
            for key in ("samples", "data", "items"):
                if key in multi_round_data and isinstance(multi_round_data[key], list):
                    multi_round_data = multi_round_data[key]
                    break
            else:
                vals = list(multi_round_data.values())
                if vals and all(isinstance(v, dict) and "trajectory" in v for v in vals):
                    multi_round_data = vals
                else:
                    print(f"Warning: Cannot recognize sample structure in input file. Expected a list of samples or a single sample with 'trajectory' key, skipping")
                    return

    if not isinstance(multi_round_data, list):
        print(f"Error: Parsed input is not a sample list, type={type(multi_round_data)}")
        return

    # 3. Iterate through each multi-round sample and split the trajectory
    for sample_idx, multi_sample in enumerate(multi_round_data):
        # Extract and keep the complete task_info if available
        task_info = multi_sample.get("task_info", {}) if isinstance(multi_sample, dict) else {}
        
        # Extract trajectory steps
        trajectory = multi_sample.get("trajectory", [])
        if not trajectory:
            print(f"Warning: Sample {sample_idx} has no trajectory data, skipping")
            continue

        # 4. Split each trajectory step into a single-round sample (retain all step details)
        for step_data in trajectory:
            # Add step index to the original task_info
            single_task_info = dict(task_info)
            if isinstance(step_data, dict):
                single_task_info["step"] = step_data.get("step", 0)
                single_step_detail = step_data.copy()
            else:
                single_task_info["step"] = 0
                single_step_detail = step_data

            single_sample = {
                "task_info": single_task_info,
                "step_detail": single_step_detail
            }
            single_round_data.append(single_sample)

    # 5. Write the processed data to the output file
    try:
        # Write as formatted JSON array for better readability
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(single_round_data, f, indent=2, ensure_ascii=False)
        print(f"Splitting completed! Processed {len(multi_round_data)} multi-round samples, generated {len(single_round_data)} single-round samples")
        print(f"Output file path: {os.path.abspath(output_file)}")
    except PermissionError:
        print(f"Error: Permission denied to write output file {output_file}")
    except Exception as e:
        print(f"Error: Failed to write file - {str(e)}")
        

if __name__ == "__main__":
    # Modify the following paths to your actual input and output file paths
    INPUT_JSON_PATH = "/EnvScaler/result/3.add_config_change.json"
    OUTPUT_JSON_PATH = "/EnvScaler/result/4.single_splited.json"
    
    # Execute the splitting process
    split_multi_round_to_single_round(INPUT_JSON_PATH, OUTPUT_JSON_PATH)
