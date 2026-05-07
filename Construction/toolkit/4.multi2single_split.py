import json
import os

def split_multi_round_to_single_round(input_file, output_file):
    """
    将多轮轨迹的JSON文件拆分为单轮样本（保留每一步的所有信息）
    :param input_file: 输入JSON文件路径（包含多轮样本）
    :param output_file: 输出JSON文件路径（拆分后的单轮样本）
    """
    # 1. 读取输入文件，支持 JSON 或 JSONL
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            text = f.read()
    except FileNotFoundError:
        print(f"错误：输入文件 {input_file} 不存在")
        return

    # 先尝试解析为完整 JSON
    multi_round_data = None
    try:
        multi_round_data = json.loads(text)
    except Exception:
        # 作为 JSONL 逐行解析
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        items = []
        for ln in lines:
            try:
                items.append(json.loads(ln))
            except Exception:
                # 忽略解析失败的行
                continue
        multi_round_data = items

    # 2.  初始化单轮样本列表
    single_round_data = []

    # 如果顶层是 dict，尝试识别包含样本的场景
    if isinstance(multi_round_data, dict):
        if "trajectory" in multi_round_data:
            multi_round_data = [multi_round_data]
        else:
            for key in ("samples", "data", "items"):
                if key in multi_round_data and isinstance(multi_round_data[key], list):
                    multi_round_data = multi_round_data[key]
                    break
            else:
                vals = list(multi_round_data.values())
                if vals and all(isinstance(v, dict) and "trajectory" in v for v in vals):
                    multi_round_data = vals
                else:
                    print(f"警告：无法识别输入文件中的样本结构，期望顶层为样本列表或单个样本（包含 'trajectory'），跳过")
                    return

    # 如果仍然不是列表，则退出
    if not isinstance(multi_round_data, list):
        print(f"错误：解析后输入不是样本列表，类型={type(multi_round_data)}")
        return

    # 3. 遍历每个多轮样本，拆分轨迹
    for sample_idx, multi_sample in enumerate(multi_round_data):
        # 提取并保留完整的 task_info（如果有）
        task_info = multi_sample.get("task_info", {}) if isinstance(multi_sample, dict) else {}
        
        # 提取轨迹步骤
        trajectory = multi_sample.get("trajectory", [])
        if not trajectory:
            print(f"警告：样本 {sample_idx} 无轨迹数据，跳过")
            continue

        # 4. 拆分每个轨迹步骤为单轮样本（保留所有步骤信息）
        for step_data in trajectory:
            # 在原 task_info 基础上加入 step 字段
            single_task_info = dict(task_info)
            if isinstance(step_data, dict):
                single_task_info["step"] = step_data.get("step", 0)
                single_step_detail = step_data.copy()
            else:
                single_task_info["step"] = 0
                single_step_detail = step_data

            single_sample = {
                "task_info": single_task_info,
                "step_detail": single_step_detail
            }
            single_round_data.append(single_sample)

    # 5. 将拆分后的数据写入输出文件
    try:
        # 将结果写为一个漂亮的 JSON 数组，便于阅读
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(single_round_data, f, indent=2, ensure_ascii=False)
        print(f"拆分完成！共处理 {len(multi_round_data)} 个多轮样本，生成 {len(single_round_data)} 个单轮样本")
        print(f"输出文件路径：{os.path.abspath(output_file)}")
    except PermissionError:
        print(f"错误：无权限写入输出文件 {output_file}")
    except Exception as e:
        print(f"错误：写入文件失败 - {str(e)}")

# ------------------- 脚本使用示例 -------------------
if __name__ == "__main__":
    # 请修改以下路径为实际的输入/输出文件路径
    INPUT_JSON_PATH = "/data/EnvScaler/interact_with_env/result/3.add_config_change.json"  # 原始多轮样本文件
    OUTPUT_JSON_PATH = "/data/EnvScaler/interact_with_env/result/4.single_splited.json"  # 拆分后的单轮样本文件
    
    # 执行拆分
    split_multi_round_to_single_round(INPUT_JSON_PATH, OUTPUT_JSON_PATH)