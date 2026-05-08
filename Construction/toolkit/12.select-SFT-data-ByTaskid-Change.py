# import json

# ===================== 【Configuration Area: Only modify the file paths here】 =====================
# # First file: Original file to be cleaned
# INPUT_FILE_1 = "/data/EnvScaler/interact_with_env/result/5.single_with_code.json"
# Second file: File providing the task_id blacklist to be deleted
# INPUT_FILE_2 = "/data/EnvScaler/interact_with_env/result/9.choice_final_combined-167env.json"
# New file output after cleaning (will not overwrite the original file)
# OUTPUT_FILE = "/data/EnvScaler/interact_with_env/result/16.select-SFT-data-noreasoning-selectedByEnv-Change.json"
# # ============================================================================

# def load_json(path):
#     """Load JSON file with exception handling"""
#     try:
#         with open(path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         print(f"✅ Successfully loaded: {path}")
#         return data
#     except FileNotFoundError:
#         print(f"❌ Error: File {path} does not exist!")
#         exit(1)
#     except json.JSONDecodeError:
#         print(f"❌ Error: File {path} is not in valid JSON format!")
#         exit(1)
#     except Exception as e:
#         print(f"❌ Failed to load file: {str(e)}")
#         exit(1)

# def save_json(data, path):
#     """Save the cleaned JSON file"""
#     try:
#         with open(path, "w", encoding="utf-8") as f:
#             json.dump(data, f, ensure_ascii=False, indent=2)
#         print(f"✅ Cleaning completed! File saved to: {path}")
#     except Exception as e:
#         print(f"❌ Failed to save file:{str(e)}")
#         exit(1)

# # 1. Load data from both files
# data1 = load_json(INPUT_FILE_1)  # Data to be cleaned
# data2 = load_json(INPUT_FILE_2)  # Blacklist data

# # 2. Extract all task_id to be deleted from the second file (generate blacklist)
# print("\n🔍 Extracting task_id blacklist from the second file...")
# env_id_blacklist = set()
# for sample in data2:
#     try:
#         env_id = sample["task_info"]["env_id"]
#         env_id_blacklist.add(env_id)
#     except KeyError:
#         continue

# print(f"📌 Extracted {len(task_id_blacklist)} task_ids to be deleted")

# # 3. Dual filtering: task_id not in blacklist + change_count > 2
# print("\n🧹 Cleaning the first file...")
# cleaned_data = []
# deleted_count = 0
# total_count = len(data1)

# for sample in data1:
#     try:
#         # Condition 1: The current sample's env_id is not in the blacklist
#         current_env_id = sample["task_info"]["env_id"]
#         if current_env_id in env_id_blacklist:
#             deleted_count += 1
#             continue
        
#         # Condition 2: The number of configuration changes must be greater than 2
#         change_count = sample["step_detail"]["config_change"]["change_count"]
#         if not isinstance(change_count, int) or change_count <= 2:
#             deleted_count += 1
#             continue
        
#         # Both conditions are satisfied, keep the sample
#         cleaned_data.append(sample)

#     except KeyError:
#         #  Missing key fields (task_id / change_count, etc.), delete directly
#         deleted_count += 1
#         continue

# # 4. Save the result
# save_json(cleaned_data, OUTPUT_FILE)

# # 5.Print statistics
# print(f"\n📊 Cleaning Statistics:")
# print(f"   Total original samples: {total_count}")
# print(f"   Deleted samples: {deleted_count}")
# print(f"   Remaining valid samples: {len(cleaned_data)}")

#We filtered the remaining 5000 samples based on env-id and found that there were no 'change_comunt' values greater than 2
#Can only filter based on task_id

import json

# ===================== 【Configuration Area: Only modify the file paths here】 =====================
# First file: Original file to be cleaned
INPUT_FILE_1 = "/data/EnvScaler/interact_with_env/result/5.single_with_code.json"
# Second file: File providing the task_id blacklist to be deleted
INPUT_FILE_2 = "/data/EnvScaler/interact_with_env/result/9.choice_final_combined-167env.json"
# New file output after cleaning (will not overwrite the original file)
OUTPUT_FILE = "/data/EnvScaler/interact_with_env/result/16.select-SFT-data-noreasoning-selectedByTaskid-Change.json"
# ============================================================================

def load_json(path):
    """Load JSON file with exception handling"""
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

# 2. Extract all task_id to be deleted from the second file (generate blacklist)
print("\n🔍 Extracting task_id blacklist from the second file...")
task_id_blacklist = set()
for sample in data2:
    try:
        # Extract task_id from the blacklist
        task_id = sample["task_info"]["task_id"]
        task_id_blacklist.add(task_id)
    except KeyError:
        # Skip invalid samples without task_id
        continue

print(f"📌 Extracted {len(task_id_blacklist)} task_ids to be deleted")

# 3. Dual filtering: task_id not in blacklist + change_count > 2
print("\n🧹 Cleaning the first file...")
cleaned_data = []
deleted_count = 0
total_count = len(data1)

for sample in data1:
    try:
        # Condition 1: The current sample's task_id is not in the blacklist
        current_task_id = sample["task_info"]["task_id"]
        if current_task_id in task_id_blacklist:
            deleted_count += 1
            continue
        
        # Condition 2: The number of configuration changes must be greater than 2
        change_count = sample["step_detail"]["config_change"]["change_count"]
        if not isinstance(change_count, int) or change_count <= 2:
            deleted_count += 1
            continue
        
        # Both conditions are satisfied, keep the sample
        cleaned_data.append(sample)

    except KeyError:
        # Missing key fields (task_id / change_count, etc.), delete directly
        deleted_count += 1
        continue

# 4. Save the result
save_json(cleaned_data, OUTPUT_FILE)

# 5. Print statistics
print(f"\n📊 Cleaning Statistics:")
print(f"   Total original samples: {total_count}")
print(f"   Deleted samples: {deleted_count}")
print(f"   Remaining valid samples: {len(cleaned_data)}")
