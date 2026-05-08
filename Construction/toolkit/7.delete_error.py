import json

def filter_invalid_samples(input_file: str, output_file: str):
    """
    Filter sample data: remove samples where observation.content starts with Error: <Exception>
    :param input_file: Path to the input raw sample JSON file
    :param output_file: Path to the output filtered sample JSON file
    """
    # 1. Read raw data
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            samples = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file {input_file} not found")
        return
    except json.JSONDecodeError:
        print(f"Error: {input_file} is not a valid JSON file")
        return

    if not isinstance(samples, list):
        print("Error: Raw data is not in list format")
        return

    total_count = len(samples)
    filtered_samples = []

    # 2. Iterate and filter samples
    for sample in samples:
        # Keep the sample by default unless an exception condition is met
        keep_sample = True
        
        try:
            # Get the target field layer by layer
            step_detail = sample.get("step_detail", {})
            observation = step_detail.get("observation", {})
            content = observation.get("content", "")

            # Check: content starts with the specified exception string
            if isinstance(content, str) and content.startswith("Error:"):
                keep_sample = False  # Mark for deletion

        except Exception:
            # Keep samples with abnormal field structure
            keep_sample = True

        if keep_sample:
            filtered_samples.append(sample)

    # 3. Save filtered data
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_samples, f, ensure_ascii=False, indent=2)

    # 4. Print statistics
    deleted_count = total_count - len(filtered_samples)
    print(f"✅ Processing completed!")
    print(f"📊 Total samples: {total_count}")
    print(f"🗑️ Deleted invalid samples: {deleted_count}")
    print(f"✅ Valid samples retained: {len(filtered_samples)}")
    print(f"📁 Filtered file saved to: {output_file}")

# ====================== Configuration (Modify here) ======================
if __name__ == "__main__":
    # Replace with your input file path and output file path
    INPUT_PATH = "/EnvScaler/result/6.true_samples.json"   # Raw sample file
    OUTPUT_PATH = "/EnvScaler/result/7.true_samples_delete_error.json"  # Filtered file
    # ==============================================================
    
    filter_invalid_samples(INPUT_PATH, OUTPUT_PATH)
