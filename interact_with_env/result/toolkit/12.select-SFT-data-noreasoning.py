import json

# ===================== 【配置区：仅需修改这里的文件路径】 =====================
# 第一个文件：需要被清理的原始文件
INPUT_FILE_1 = "/data/EnvScaler/interact_with_env/result/5.single_with_code.json"
# 第二个文件：提供要删除的env_id黑名单的文件
INPUT_FILE_2 = "/data/EnvScaler/interact_with_env/result/9.choice_final_combined-167env.json"
# 清理后输出的新文件（不会覆盖原文件）
OUTPUT_FILE = "/data/EnvScaler/interact_with_env/result/12.select-SFT-data-noreasoning.json"
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
    """保存清理后的JSON文件"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 清理完成！文件已保存至：{path}")
    except Exception as e:
        print(f"❌ 保存文件失败：{str(e)}")
        exit(1)

# 1. 加载两个文件的数据
data1 = load_json(INPUT_FILE_1)  # 待清理数据
data2 = load_json(INPUT_FILE_2)  # 黑名单数据

# 2. 从第二个文件提取所有需要删除的 env_id（生成黑名单）
print("\n🔍 正在提取第二个文件的 env_id 黑名单...")
env_id_blacklist = set()
for sample in data2:
    try:
        env_id = sample["task_info"]["env_id"]
        env_id_blacklist.add(env_id)
    except KeyError:
        # 跳过没有env_id的无效样本
        continue

print(f"📌 共提取到 {len(env_id_blacklist)} 个需要删除的 env_id")

# 3. 过滤第一个文件：删除所有在黑名单中的样本
print("\n🧹 正在清理第一个文件...")
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
        # 保留无env_id的样本（避免误删）
        cleaned_data.append(sample)

# 4. 保存结果
save_json(cleaned_data, OUTPUT_FILE)

# 5. 打印统计信息
print(f"\n📊 清理统计：")
print(f"   原始样本总数：{total_count}")
print(f"   删除样本数：{deleted_count}")
print(f"   剩余有效样本数：{len(cleaned_data)}")