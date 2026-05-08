import json
import os
import ast

def split_by_observation_success(input_file, true_output_file, false_output_file):
    """
    Split the dataset by the success field in observation.content
    :param input_file: Path to the input single-round JSON file
    :param true_output_file: Output path for samples with success=True
    :param false_output_file: Output path for samples with success=False
    """
    # 1. Initialize two sample lists
    success_true_samples = []
    success_false_samples = []
    error_samples = []  # Store samples that fail to parse

    # 2. Read input file
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            single_round_data = json.load(f)
        print(f"Successfully read input file, total {len(single_round_data)} samples")
    except FileNotFoundError:
        print(f"Error: Input file {input_file} does not exist")
        return
    except json.JSONDecodeError:
        print(f"Error: Input file {input_file} is not in valid JSON format")
        return

    # 3. Iterate over each sample and determine success status
    for idx, sample in enumerate(single_round_data):
        try:
            # Extract observation.content field
            step_detail = sample.get("step_detail", {})
            observation = step_detail.get("observation", {})
            content_str = observation.get("content", "{}")

            # Parse content string (compatible with single/double quote JSON format)
            # Try multiple strategies: literal_eval -> regex extraction -> infer from text keywords
            success_status = False
            content_data = None
            try:
                # If content looks like a literal structure (starts with { or [), try parsing first
                if isinstance(content_str, (dict, list)):
                    content_data = content_str
                else:
                    s = str(content_str).strip()
                    if s.startswith('{') or s.startswith('['):
                        try:
                            content_data = ast.literal_eval(s)
                        except Exception:
                            # Try json.loads instead (handle double quote JSON)
                            try:
                                content_data = json.loads(s)
                            except Exception:
                                content_data = None
                    else:
                        content_data = None

                # If structure is parsed, try to read success field
                if isinstance(content_data, dict):
                    success_status = content_data.get('success', content_data.get('succeed', False))
                else:
                    # 1) Directly search for success: true/false in text
                    import re
                    text = str(content_str)
                    m = re.search(r"['\"]?success['\"]?\s*:\s*(True|False|true|false|1|0)", text)
                    if m:
                        val = m.group(1)
                        success_status = True if val.lower() in ('true', '1') else False
                    else:
                        # 2) Infer based on common keywords (e.g. contains 'completed'/'finished' -> True)
                        tl = text.lower()
                        if any(k in tl for k in ('completed', 'task completed', 'finished', 'success', 'succeeded')):
                            success_status = True
                        elif any(k in tl for k in ('failed', 'error', 'unsuccess', 'failed to')):
                            success_status = False
                        else:
                            # 3) Use terminated field in step_detail as a weak signal if available
                            terminated = step_detail.get('terminated')
                            if isinstance(terminated, bool):
                                success_status = bool(terminated)
                            else:
                                # Fallback to False
                                success_status = False

                # Normalize Python True/False strings
                if isinstance(success_status, str):
                    success_status = success_status.lower() in ('true', '1', 'yes')
                else:
                    success_status = bool(success_status)

            except Exception as e:
                # If all strategies fail, log parsing error and continue (classify sample as success=False)
                error_samples.append({
                    "sample_index": idx,
                    "error": str(e),
                    "sample": sample
                })
                print(f"Warning: Failed to parse sample {idx} - {str(e)}")

            # Store samples by category
            if success_status:
                success_true_samples.append(sample)
            else:
                success_false_samples.append(sample)

        except (SyntaxError, ValueError, TypeError) as e:
            # Log failed samples without interrupting the process
            error_samples.append({
                "sample_index": idx,
                "error": str(e),
                "sample": sample
            })
            print(f"Warning: Failed to parse sample {idx} - {str(e)}")
        except Exception as e:
            error_samples.append({
                "sample_index": idx,
                "error": str(e),
                "sample": sample
            })
            print(f"Warning: Exception processing sample {idx} - {str(e)}")

    # 4. Write samples to files
    def write_samples(samples, output_path, label):
        """Helper function: write samples and print statistics"""
        if not samples:
            print(f"⚠️ No {label} samples, skip writing")
            return
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(samples, f, indent=2, ensure_ascii=False)
            print(f"✅ {label} samples written: {len(samples)}, path: {os.path.abspath(output_path)}")
        except PermissionError:
            print(f"❌ No permission to write {label} sample file: {output_path}")
        except Exception as e:
            print(f"❌ Failed to write {label} samples: {str(e)}")


    # Write two datasets
    write_samples(success_true_samples, true_output_file, "success=True")
    write_samples(success_false_samples, false_output_file, "success=False")

    # 5. Print final statistics
    print("\n=== Split Statistics ===")
    print(f"Total samples: {len(single_round_data)}")
    print(f"success=True samples: {len(success_true_samples)}")
    print(f"success=False samples: {len(success_false_samples)}")
    print(f"Failed parsing samples: {len(error_samples)}")

    # Optional: Write failed parsing samples to file
    if error_samples:
        error_file = "error_samples.json"
        with open(error_file, 'w', encoding='utf-8') as f:
            json.dump(error_samples, f, indent=2, ensure_ascii=False)
        print(f"⚠️ Failed parsing samples have been written to: {os.path.abspath(error_file)}")

# ------------------- Script Usage Example -------------------
if __name__ == "__main__":
    # Modify the following paths to actual file paths
    INPUT_FILE = "/EnvScaler/result/5.single_with_code.json"  # Original single-round dataset
    TRUE_OUTPUT_FILE = "/EnvScaler/result/6.true_samples.json"  # Dataset with success=True
    FALSE_OUTPUT_FILE = "/EnvScaler/result/6.false_samples.json"  # Dataset with success=False
    
    # Execute splitting
    split_by_observation_success(INPUT_FILE, TRUE_OUTPUT_FILE, FALSE_OUTPUT_FILE)
