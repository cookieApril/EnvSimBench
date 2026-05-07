import json
import random
import os

def create_dataset_subsets(input_file, output_dir, target_sizes, seed=42):
    """
    读取原始数据并根据指定数量生成嵌套的随机子集。
    """
    print(f"正在加载原始数据文件: {input_file}...")
    data = []
    
    # 假设数据是 JSONL 格式（每行一个完整独立的 JSON）
    # 如果你的数据是一个巨大的 JSON 数组 [...]，请改用: data = json.load(open(input_file, 'r', encoding='utf-8'))
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
                
    total_samples = len(data)
    print(f"成功加载，共 {total_samples} 条数据。")

    # 使用固定的随机种子打乱数据，保证每次运行结果一致可复现
    random.seed(seed)
    random.shuffle(data)

    # 创建输出文件夹
    os.makedirs(output_dir, exist_ok=True)

    # 按照目标数量切片生成数据集
    for size in target_sizes:
        # 如果要求的数据量大于实际数据量，则向下取实际最大值
        actual_size = min(size, total_samples)
        
        # 采用从头切片的方式，确保 1K ⊂ 2K ⊂ 5K ⊂ 10K ...
        
        subset = data[:actual_size]
        
        # 格式化输出文件名
        size_label = f"{actual_size // 1000}K" if actual_size >= 1000 else str(actual_size)
        output_file = os.path.join(output_dir, f"env_dataset_sft_{size_label}.jsonl")
        
        # 写入文件，确保不破坏原有的非 ASCII 字符（如中文或特殊符号）
        with open(output_file, 'w', encoding='utf-8') as f_out:
            for item in subset:
                f_out.write(json.dumps(item, ensure_ascii=False) + '\n')
                
        print(f"已生成 {size_label} 数据集 -> {output_file} (包含 {actual_size} 条样本)")

if __name__ == "__main__":
    # 配置参数
    INPUT_FILE = '/data/EnvScaler/interact_with_env/result/14.sft_data_final-selectByTask.jsonl'  # 替换为你的 5w+ 条数据的原始文件名
    OUTPUT_DIR = '/data/EnvScaler/interact_with_env/result/15.split-Number-Set'             # 生成的数据集存放的目录
    TARGET_SIZES = [1000, 2000, 5000, 10000, 20000, 50000] # 你需要的各个梯度规模
    
    create_dataset_subsets(INPUT_FILE, OUTPUT_DIR, TARGET_SIZES)


