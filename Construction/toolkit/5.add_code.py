import json
import ijson
from decimal import Decimal
import traceback

# ===================== You Files Path =====================
DATA_PATH = "/EnvScaler/result/4.single_splited.json"
CODE_PATH = "/EnvScaler/seed/191_env_metadata.json"
OUTPUT_PATH = "/EnvScaler/result/5.single_with_code.json"
# =========================================================

# Custom JSON encoder: fix Decimal serialization issue
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

def main():
    print("Loading env metadata file...")
    with open(CODE_PATH, "r", encoding="utf-8") as f:
        code_map = json.load(f)

    print("Starting to stream read JSON file...\n")
    valid_data = []
    error_count = 0

    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            for idx, item in enumerate(ijson.items(f, "item"), 1):
                if idx % 100000 == 0:
                    print(f"Parsed: {idx:,} items")

                # Core processing logic + detailed error catching
                try:
                    env_id = item["task_info"]["env_id"]
                    if env_id in code_map:
                        item["env_code"] = code_map[env_id]["env_class_code"]
                    valid_data.append(item)

                # Error in single item: print full error context
                except Exception as e:
                    error_count += 1
                    print(f"\n❌ Failed to parse item {idx}!")
                    print(f"Error Type: {type(e).__name__}")
                    print(f"Error Message: {str(e)}")
                    print(f"Error Data Snippet: {str(item)[:500]}...")
                    print("-" * 80)
                    continue

    except json.JSONDecodeError:
        print("\n⚠️ File truncated at the end, stopped parsing, retaining all valid data")
    except Exception as e:
        print(f"\n⚠️ File reading exception: {str(e)}")
        traceback.print_exc()

    print(f"\n📊 Statistics:")
    print(f"✅ Valid items: {len(valid_data)}")
    print(f"❌ Invalid items: {error_count}")

    # Save file + catch serialization errors
    print("\nSaving file...")
    try:
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(
                valid_data,
                f,
                ensure_ascii=False,
                indent=4,
                cls=DecimalEncoder
            )
        print(f"\n🎉 Saved successfully! File path: {OUTPUT_PATH}")

    # Serialization error: print specific error object
    except Exception as e:
        print(f"\n❌ Failed to save file! Serialization error:")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
