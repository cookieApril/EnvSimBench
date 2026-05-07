import json

def filter_invalid_samples(input_file: str, output_file: str):
    """
    过滤样本数据：删除observation.content以Error: <Exception>开头的样本
    :param input_file: 输入的原始样本JSON文件路径
    :param output_file: 输出的过滤后样本JSON文件路径
    """
    # 1. 读取原始数据
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            samples = json.load(f)
    except FileNotFoundError:
        print(f"错误：未找到输入文件 {input_file}")
        return
    except json.JSONDecodeError:
        print(f"错误：{input_file} 不是合法的JSON文件")
        return

    if not isinstance(samples, list):
        print("错误：原始数据不是列表格式")
        return

    total_count = len(samples)
    filtered_samples = []

    # 2. 遍历过滤样本
    for sample in samples:
        # 默认保留样本，除非命中异常条件
        keep_sample = True
        
        try:
            # 逐层获取目标字段
            step_detail = sample.get("step_detail", {})
            observation = step_detail.get("observation", {})
            content = observation.get("content", "")

            # 判断：content以指定异常字符串开头
            if isinstance(content, str) and content.startswith("Error:"):
                keep_sample = False  # 标记删除

        except Exception:
            # 字段结构异常的样本，直接保留
            keep_sample = True

        if keep_sample:
            filtered_samples.append(sample)

    # 3. 保存过滤后的数据
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(filtered_samples, f, ensure_ascii=False, indent=2)

    # 4. 打印统计信息
    deleted_count = total_count - len(filtered_samples)
    print(f"✅ 处理完成！")
    print(f"📊 总样本数：{total_count}")
    print(f"🗑️  删除异常样本：{deleted_count}")
    print(f"✅ 保留有效样本：{len(filtered_samples)}")
    print(f"📁 过滤后文件已保存至：{output_file}")

# ====================== 配置区（修改这里即可）======================
if __name__ == "__main__":
    # 替换为你的 输入文件路径 和 输出文件路径
    INPUT_PATH = "/data/EnvScaler/interact_with_env/result/6.true_samples.json"   # 原始样本文件
    OUTPUT_PATH = "/data/EnvScaler/interact_with_env/result/7.true_samples_delete_error.json"  # 过滤后的文件
    # ==============================================================
    
    filter_invalid_samples(INPUT_PATH, OUTPUT_PATH)