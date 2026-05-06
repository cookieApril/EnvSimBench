# import json

# # ===================== 【配置区：仅需修改这里的文件路径】 =====================
# # 第一个文件：需要被清理的原始文件
# INPUT_FILE_1 = "/data/EnvScaler/interact_with_env/result/5.single_with_code.json"
# # 第二个文件：提供要删除的env_id黑名单的文件
# INPUT_FILE_2 = "/data/EnvScaler/interact_with_env/result/9.choice_final_combined-167env.json"
# # 清理后输出的新文件（不会覆盖原文件）
# OUTPUT_FILE = "/data/EnvScaler/interact_with_env/result/16.select-SFT-data-noreasoning-selectedByEnv-Change.json"
# # ============================================================================

# def load_json(path):
#     """加载JSON文件，带异常处理"""
#     try:
#         with open(path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         print(f"✅ 成功加载：{path}")
#         return data
#     except FileNotFoundError:
#         print(f"❌ 错误：文件 {path} 不存在！")
#         exit(1)
#     except json.JSONDecodeError:
#         print(f"❌ 错误：文件 {path} 不是合法的JSON格式！")
#         exit(1)
#     except Exception as e:
#         print(f"❌ 加载文件失败：{str(e)}")
#         exit(1)

# def save_json(data, path):
#     """保存清理后的JSON文件"""
#     try:
#         with open(path, "w", encoding="utf-8") as f:
#             json.dump(data, f, ensure_ascii=False, indent=2)
#         print(f"✅ 清理完成！文件已保存至：{path}")
#     except Exception as e:
#         print(f"❌ 保存文件失败：{str(e)}")
#         exit(1)

# # 1. 加载两个文件的数据
# data1 = load_json(INPUT_FILE_1)  # 待清理数据
# data2 = load_json(INPUT_FILE_2)  # 黑名单数据

# # 2. 从第二个文件提取所有需要删除的 env_id（生成黑名单）
# print("\n🔍 正在提取第二个文件的 env_id 黑名单...")
# env_id_blacklist = set()
# for sample in data2:
#     try:
#         env_id = sample["task_info"]["env_id"]
#         env_id_blacklist.add(env_id)
#     except KeyError:
#         # 跳过没有env_id的无效样本
#         continue

# print(f"📌 共提取到 {len(env_id_blacklist)} 个需要删除的 env_id")

# # 3. 过滤第一个文件：删除所有在黑名单中的样本
# print("\n🧹 正在清理第一个文件...")
# cleaned_data = []
# deleted_count = 0
# total_count = len(data1)

# for sample in data1:
#     try:
#         # 条件1：检查 env_id
#         current_env_id = sample["task_info"]["env_id"]
#         if current_env_id in env_id_blacklist:
#             deleted_count += 1
#             continue
        
#         # 条件2：检查 change_count > 2
#         change_count = sample["step_detail"]["config_change"]["change_count"]
#         if not isinstance(change_count, int) or change_count <= 2:
#             deleted_count += 1
#             continue
        
#         # 两个条件都满足，保留样本
#         cleaned_data.append(sample)

#     except KeyError:
#         # 缺少任意关键字段（env_id/step_detail/config_change），直接删除
#         deleted_count += 1
#         continue

# # 4. 保存结果
# save_json(cleaned_data, OUTPUT_FILE)

# # 5. 打印统计信息
# print(f"\n📊 清理统计：")
# print(f"   原始样本总数：{total_count}")
# print(f"   删除样本数：{deleted_count}")
# print(f"   剩余有效样本数：{len(cleaned_data)}")

#我们根据env_id筛选剩余的5000条样本中没有"change_count":>2的
#只能根据task_id筛选

# import json

# # ===================== 【配置区：仅需修改这里的文件路径】 =====================
# # 第一个文件：需要被清理的原始文件
# INPUT_FILE_1 = "/data/EnvScaler/interact_with_env/result/5.single_with_code.json"
# # 第二个文件：提供要删除的 task_id 黑名单的文件
# INPUT_FILE_2 = "/data/EnvScaler/interact_with_env/result/9.choice_final_combined-167env.json"
# # 清理后输出的新文件
# OUTPUT_FILE = "/data/EnvScaler/interact_with_env/result/16.select-SFT-data-noreasoning-selectedByTaskid-Change.json"
# # ============================================================================

# def load_json(path):
#     """加载JSON文件，带异常处理"""
#     try:
#         with open(path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         print(f"✅ 成功加载：{path}")
#         return data
#     except FileNotFoundError:
#         print(f"❌ 错误：文件 {path} 不存在！")
#         exit(1)
#     except json.JSONDecodeError:
#         print(f"❌ 错误：文件 {path} 不是合法的JSON格式！")
#         exit(1)
#     except Exception as e:
#         print(f"❌ 加载文件失败：{str(e)}")
#         exit(1)

# def save_json(data, path):
#     """保存清理后的JSON文件"""
#     try:
#         with open(path, "w", encoding="utf-8") as f:
#             json.dump(data, f, ensure_ascii=False, indent=2)
#         print(f"✅ 清理完成！文件已保存至：{path}")
#     except Exception as e:
#         print(f"❌ 保存文件失败：{str(e)}")
#         exit(1)

# # 1. 加载两个文件的数据
# data1 = load_json(INPUT_FILE_1)  # 待清理数据
# data2 = load_json(INPUT_FILE_2)  # 黑名单数据

# # 2. 从第二个文件提取所有需要删除的 task_id（生成黑名单）
# print("\n🔍 正在提取第二个文件的 task_id 黑名单...")
# task_id_blacklist = set()
# for sample in data2:
#     try:
#         # 提取黑名单的 task_id
#         task_id = sample["task_info"]["task_id"]
#         task_id_blacklist.add(task_id)
#     except KeyError:
#         # 跳过没有task_id的无效样本
#         continue

# print(f"📌 共提取到 {len(task_id_blacklist)} 个需要删除的 task_id")

# # 3. 双重过滤：task_id不在黑名单 + change_count > 2
# print("\n🧹 正在清理第一个文件...")
# cleaned_data = []
# deleted_count = 0
# total_count = len(data1)

# for sample in data1:
#     try:
#         # 条件1：当前样本的 task_id 不在黑名单中
#         current_task_id = sample["task_info"]["task_id"]
#         if current_task_id in task_id_blacklist:
#             deleted_count += 1
#             continue
        
#         # 条件2：配置变更数量必须大于 2
#         change_count = sample["step_detail"]["config_change"]["change_count"]
#         if not isinstance(change_count, int) or change_count <= 2:
#             deleted_count += 1
#             continue
        
#         # 两个条件全部满足，保留样本
#         cleaned_data.append(sample)

#     except KeyError:
#         # 缺少 task_id / change_count 等关键字段，直接删除
#         deleted_count += 1
#         continue

# # 4. 保存结果
# save_json(cleaned_data, OUTPUT_FILE)

# # 5. 打印统计信息
# print(f"\n📊 清理统计：")
# print(f"   原始样本总数：{total_count}")
# print(f"   删除样本数：{deleted_count}")
# print(f"   剩余有效样本数：{len(cleaned_data)}")




#均衡样本数量
import json
import random
import ast  # 新增：用于解析字符串形式的字典

# 设置随机种子，保证采样结果可复现（可删除）
random.seed(42)

# ===================== 【配置区：仅需修改这里的文件路径和采样数量】 =====================
# 第一个文件：需要被清理的原始文件
INPUT_FILE_1 = "/data/EnvScaler/interact_with_env/result/5.single_with_code.json"
# 第二个文件：提供要删除的 task_id 黑名单的文件
INPUT_FILE_2 = "/data/EnvScaler/interact_with_env/result/9.choice_final_combined-167env.json"
# 清理后输出的新文件
OUTPUT_FILE = "/data/EnvScaler/interact_with_env/result/12.select-SFT-data-noreasoning-selectedByTaskid-Change-balance2.json"

# 各组采样数量配置
SAMPLE_FAILURE = 1000                # observation.success=False 的样本，采样1000个
SAMPLE_SUCCESS_ZERO = 1000           # observation.success=True 且 change_count=0 的样本，采样1000个
SAMPLE_SUCCESS_ONE_TWO = 2000        # observation.success=True 且 0<change_count<3 的样本，采样2000个
# observation.success=True 且 change_count>=3 的样本，全部保留，无需采样
# ======================================================================================

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
        print(f"✅ 采样完成！文件已保存至：{path}")
    except Exception as e:
        print(f"❌ 保存文件失败：{str(e)}")
        exit(1)

# 采样函数：不足则取全部
def sample_group(group, name, count):
    sampled = random.sample(group, min(count, len(group)))
    print(f"📦 {name}：原始 {len(group)} 条 → 采样 {len(sampled)} 条")
    return sampled

# 1. 加载两个文件的数据
data1 = load_json(INPUT_FILE_1)  # 待采样数据
data2 = load_json(INPUT_FILE_2)  # 黑名单数据

# 2. 从第二个文件提取所有需要删除的 task_id（生成黑名单）
print("\n🔍 正在提取第二个文件的 task_id 黑名单...")
task_id_blacklist = set()
for sample in data2:
    try:
        task_id = sample["task_info"]["task_id"]
        task_id_blacklist.add(task_id)
    except KeyError:
        continue

print(f"📌 共提取到 {len(task_id_blacklist)} 个需要排除的 task_id")

# 3. 第一步：过滤黑名单 + 按新规则分组
print("\n🧩 正在分组筛选数据...")
# 初始化四个分组
group_failure = []                # success=False
group_success_zero = []           # success=True, change_count=0
group_success_one_two = []        # success=True, 0<change_count<3
group_success_over_three = []     # success=True, change_count>=3
total_original = len(data1)

for sample in data1:
    try:
        # 条件1：排除黑名单
        current_task_id = sample["task_info"]["task_id"]
        if current_task_id in task_id_blacklist:
            continue
        
        # 解析observation的content，获取success状态
        obs_content = sample["step_detail"]["observation"]["content"]
        # 如果content是字符串，解析成字典；如果已经是字典，直接使用
        if isinstance(obs_content, str):
            obs_content = ast.literal_eval(obs_content)
        success = obs_content["success"]
        
        # 获取change_count并校验类型
        change_count = sample["step_detail"]["config_change"]["change_count"]
        if not isinstance(change_count, int):
            continue

        # 按规则分组
        if not success:
            group_failure.append(sample)
        else:
            if change_count == 0:
                group_success_zero.append(sample)
            elif 0 < change_count < 3:
                group_success_one_two.append(sample)
            elif change_count >= 3:
                group_success_over_three.append(sample)
            # change_count == 3 的样本未匹配规则，自动过滤

    except Exception:
        # 任何异常（缺少字段、格式错误等），跳过该样本
        continue

# 4. 第二步：按规则对各组进行采样
print(f"\n🎲 开始按规则采样...")

sampled_failure = sample_group(group_failure, "success=False", SAMPLE_FAILURE)
sampled_success_zero = sample_group(group_success_zero, "success=True & change_count=0", SAMPLE_SUCCESS_ZERO)
sampled_success_one_two = sample_group(group_success_one_two, "success=True & 0<change_count<3", SAMPLE_SUCCESS_ONE_TWO)
# change_count>3的组全部保留，无需采样
sampled_success_over_three = group_success_over_three
print(f"📦 success=True & change_count>3：原始 {len(group_success_over_three)} 条 → 全部保留")

# 5. 合并最终数据
cleaned_data = sampled_failure + sampled_success_zero + sampled_success_one_two + sampled_success_over_three

# 6. 保存结果
save_json(cleaned_data, OUTPUT_FILE)

# 7. 打印统计信息
print(f"\n📊 最终统计：")
print(f"   原始样本总数：{total_original}")
filtered_count = total_original - len(group_failure) - len(group_success_zero) - len(group_success_one_two) - len(group_success_over_three)
print(f"   黑名单排除 + 无效字段/格式错误：{filtered_count} 条")
print(f"   success=False 最终保留：{len(sampled_failure)} 条")
print(f"   success=True & change_count=0 最终保留：{len(sampled_success_zero)} 条")
print(f"   success=True & 0<change_count<3 最终保留：{len(sampled_success_one_two)} 条")
print(f"   success=True & change_count>3 最终保留：{len(sampled_success_over_three)} 条")
print(f"   输出文件总样本数：{len(cleaned_data)}")
