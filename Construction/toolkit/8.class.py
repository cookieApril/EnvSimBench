import json
import os
import ijson
from decimal import Decimal  

#Custom JSON encoder to handle Decimal type
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        # Handle Decimal type: convert to string (recommended, preserves precision) or float (choose as needed)
        if isinstance(obj, Decimal):
            # Option 1: Convert to string (recommended, no precision loss)
            return str(obj)
            # Option 2: Convert to float (if high precision is not required, only numerical value)
            # return float(obj)
        # Handle other non-serializable types (optional, prevent subsequent errors)
        elif isinstance(obj, (int, float, str, list, dict, bool, type(None))):
            return super().default(obj)
        else:
            # Convert other unknown types to string to avoid script interruption
            print(f"Warning: Unknown type {type(obj)} detected, converted to string")
            return str(obj)

def read_large_json_array_ijson(file_path: str):
    """
    Stream parse ultra-large JSON array with ijson (supports single/multi-line JSON), return objects one by one, high efficiency
    :param file_path: Path to the ultra-large JSON array file
    :return: Return sample dictionaries one by one
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Stream parse each element in the JSON array (item is a single sample in the array)
            print("Start streaming parsing JSON array (ijson)...")
            # ijson.items(file handle, "item") parses each element of the JSON array specifically
            for idx, sample in enumerate(ijson.items(f, "item"), 1):
                if idx % 10 == 0:
                    print(f"Parsed {idx} samples (ijson streaming parsing)")
                yield sample
            print(f"JSON parsing completed, total {idx if 'idx' in locals() else 0} samples parsed")
    except Exception as e:
        print(f"ijson JSON parsing failed: {e}")
        raise

def group_samples_by_change_count_streaming(json_file: str, output_prefix: str = "/EnvScaler/result/7.true_samples_change_count"):
    """
    Stream read JSON file, group by change_count, and write to corresponding JSON files in real-time.
    """
    # Ensure output directory exists
    output_dir = os.path.dirname(output_prefix)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"Create/verify output directory: {output_dir}")
    
    # Store file handles and first element write status for each change_count
    file_handles = {}          
    first_element_written = {} 

    try:
        sample_count = 0
        # Use ijson parsing function (core modification)
        for sample in read_large_json_array_ijson(json_file):
            sample_count += 1
            
            # Extract change_count
            try:
                change_count = sample.get("step_detail", {}).get("config_change", {}).get("change_count")
                if change_count is None:
                    print(f"\nWarning: Sample {sample_count} missing change_count, skipped. Sample ID: {sample.get('task_info', {}).get('task_id', 'Unknown')}")
                    continue
                change_count = str(change_count)
            except Exception as e:
                print(f"\nFailed to parse change_count for sample {sample_count}: {e}")
                continue

            # Create/open file for corresponding change_count
            if change_count not in file_handles:
                filename = f"{output_prefix}_{change_count}.json"
                f = open(filename, 'w', encoding='utf-8')
                f.write('[\n')
                file_handles[change_count] = f
                first_element_written[change_count] = False
                print(f"\nCreated file and started writing: {filename}")

            f = file_handles[change_count]

            # Write sample (handle comma separation)
            if first_element_written[change_count]:
                f.write(',\n')
            else:
                first_element_written[change_count] = True

            #Use custom encoder to handle Decimal type
            json.dump(sample, f, ensure_ascii=False, indent=2, cls=DecimalEncoder)
            f.flush()
            os.fsync(f.fileno())  # Force flush to disk

            # Print total progress every 50 processed samples
            if sample_count % 50 == 0:
                print(f"Total processing progress: Processed {sample_count} samples, created {len(file_handles)} group files")

        print(f"\n✅ Processing completed! Total samples processed: {sample_count}, generated {len(file_handles)} group files")

    except Exception as e:
        print(f"\n❌ Error occurred while processing samples: {e}")
        raise
    finally:
        # Close all files and complete JSON array closing bracket
        for change_count, f in file_handles.items():
            try:
                f.write('\n]')
                f.flush()
                os.fsync(f.fileno())
                f.close()
                print(f"✅ File writing completed and closed: {output_prefix}_{change_count}.json")
            except Exception as e:
                print(f"❌ Error closing file {change_count}: {e}")


if __name__ == "__main__":
    input_file = "/EnvScaler/result/9.choice_final_combined.json"
    print(f"🚀 Start processing ultra-large JSON file: {input_file}")
    # Check if file exists
    if not os.path.exists(input_file):
        print(f"❌ Error: Input file does not exist → {input_file}")
    else:
        # Check file size (confirm it's an ultra-large file)
        file_size = os.path.getsize(input_file) / (1024*1024)  # Convert to MB
        print(f"📄 File size: {file_size:.2f} MB")
        group_samples_by_change_count_streaming(input_file)
