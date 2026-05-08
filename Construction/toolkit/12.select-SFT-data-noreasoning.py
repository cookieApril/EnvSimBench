import json

# ===================== [Configuration Area: Only modify file paths here] =====================
# First file: The original file to be cleaned
INPUT_FILE_1 = "/EnvScaler/result/5.single_with_code.json"
# Second file: File containing the env_id blacklist to be removed
INPUT_FILE_2 = "/EnvScaler/result/9.choice_final_combined-167env.json"
# Output file after cleaning (will not overwrite the original files)
OUTPUT_FILE = "/EnvScaler/result/12.select-SFT-data-noreasoning.json"
# ============================================================================================

def load_json(path):
    """Load JSON file with error handling"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"✅ Successfully loaded: {path}")
        return data
    except FileNotFoundError:
        print(f"❌ Error: File {path} does not exist!")
        exit(1)
    except json.JSONDecodeError:
        print(f"❌ Error: File {path} is not in valid JSON format!")
        exit(1)
    except Exception as e:
        print(f"❌ Failed to load file: {str(e)}")
        exit(1)

def save_json(data, path):
    """Save the cleaned JSON file"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Cleaning completed! File saved to: {path}")
    except Exception as e:
        print(f"❌ Failed to save file: {str(e)}")
        exit(1)

# 1. Load data from both files
data1 = load_json(INPUT_FILE_1)  # Data to be cleaned
data2 = load_json(INPUT_FILE_2)  # Blacklist data

# 2. Extract all env_ids to be removed from the second file (generate blacklist)
print("\n🔍 Extracting env_id blacklist from the second file...")
env_id_blacklist = set()
for sample in data2:
    try:
        env_id = sample["task_info"]["env_id"]
        env_id_blacklist.add(env_id)
    except KeyError:
        # Skip invalid samples without env_id
        continue

print(f"📌 Extracted {len(env_id_blacklist)} env_ids to be removed")

# 3. Filter the first file: remove all samples in the blacklist
print("\n🧹 Cleaning the first file...")
cleaned_data = []
deleted_count = 0
total_count = len(data1)

for sample in data1:
    try:
        current_env_id = sample["task_info"]["env_id"]
        if current_env_id not in env_id_blacklist:
            cleaned_data.append(sample)
        else:
            deleted_count += 1
    except KeyError:
        # Keep samples without env_id (avoid accidental deletion)
        cleaned_data.append(sample)

# 4. Save the result
save_json(cleaned_data, OUTPUT_FILE)

# 5. Print statistics
print(f"\n📊 Cleanup Statistics:")
print(f"   Total original samples: {total_count}")
print(f"   Deleted samples: {deleted_count}")
print(f"   Remaining valid samples: {len(cleaned_data)}")


