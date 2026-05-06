import json

# ===================== 【配置区：仅需修改这里的文件路径】 =====================
# 要拼接的第一个JSON文件
INPUT_FILE_A = "/data/EnvScaler/interact_with_env/result/12.select-SFT-data-noreasoning-selectedByTaskid-Change.json"
# 要拼接的第二个JSON文件
INPUT_FILE_B = "/data/EnvScaler/interact_with_env/result/12.select-SFT-data-noreasoning-selectedByTaskid-Change-balance.json"
# 拼接后输出的新文件
OUTPUT_FILE = "/data/EnvScaler/interact_with_env/result/12.select-SFT-data-noreasoning-selectedByTaskid-Change-balance1.json"
# ============================================================================

def load_json(path):
    """加载JSON文件，带异常处理"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"✅ 成功加载：{path}")
        return data
    except FileNotFoundError:
        print(f"❌ 错误：文件 {path} 不存在！")
        exit(1)
    except json.JSONDecodeError:
        print(f"❌ 错误：文件 {path} 不是合法的JSON格式！")
        exit(1)
    except Exception as e:
        print(f"❌ 加载文件失败：{str(e)}")
        exit(1)

def save_json(data, path):
    """保存合并后的JSON文件"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 合并完成！文件已保存至：{path}")
    except Exception as e:
        print(f"❌ 保存文件失败：{str(e)}")
        exit(1)

# 1. 加载两个文件
data_a = load_json(INPUT_FILE_A)
data_b = load_json(INPUT_FILE_B)

# 2. 核心：拼接两个JSON数组（直接列表相加）
merged_data = data_a + data_b

# 3. 保存合并结果
save_json(merged_data, OUTPUT_FILE)

# 4. 打印统计信息
print(f"\n📊 合并统计：")
print(f"   文件A样本数：{len(data_a)}")
print(f"   文件B样本数：{len(data_b)}")
print(f"   合并后总样本数：{len(merged_data)}")