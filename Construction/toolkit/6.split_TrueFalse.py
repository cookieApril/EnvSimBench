import json
import os
import ast

def split_by_observation_success(input_file, true_output_file, false_output_file):
    """
    按observation.content中的success字段拆分数据集
    :param input_file: 输入单轮化后的JSON文件路径
    :param true_output_file: success=True的样本输出路径
    :param false_output_file: success=False的样本输出路径
    """
    # 1. 初始化两个样本列表
    success_true_samples = []
    success_false_samples = []
    error_samples = []  # 存储解析失败的样本

    # 2. 读取输入文件
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            single_round_data = json.load(f)
        print(f"成功读取输入文件，共 {len(single_round_data)} 个样本")
    except FileNotFoundError:
        print(f"错误：输入文件 {input_file} 不存在")
        return
    except json.JSONDecodeError:
        print(f"错误：输入文件 {input_file} 不是合法的JSON格式")
        return

    # 3. 遍历每个样本，判断success状态
    for idx, sample in enumerate(single_round_data):
        try:
            # 提取observation.content字段
            step_detail = sample.get("step_detail", {})
            observation = step_detail.get("observation", {})
            content_str = observation.get("content", "{}")

            # 解析content字符串（兼容单引号/双引号的JSON格式）
            # 尝试多种策略：literal_eval -> regex提取 -> 根据文本关键词推断
            success_status = False
            content_data = None
            try:
                # 若content看起来像字面量结构（以{或[开头），优先尝试解析
                if isinstance(content_str, (dict, list)):
                    content_data = content_str
                else:
                    s = str(content_str).strip()
                    if s.startswith('{') or s.startswith('['):
                        try:
                            content_data = ast.literal_eval(s)
                        except Exception:
                            # 尝试用json.loads替代（处理双引号JSON）
                            try:
                                content_data = json.loads(s)
                            except Exception:
                                content_data = None
                    else:
                        content_data = None

                # 如果解析出结构，尝试读取success字段
                if isinstance(content_data, dict):
                    success_status = content_data.get('success', content_data.get('succeed', False))
                else:
                    # 1) 直接在文本中搜索 success: true/false
                    import re
                    text = str(content_str)
                    m = re.search(r"['\"]?success['\"]?\s*:\s*(True|False|true|false|1|0)", text)
                    if m:
                        val = m.group(1)
                        success_status = True if val.lower() in ('true', '1') else False
                    else:
                        # 2) 根据常见关键词推断（例如含有 'completed'/'finished' -> True）
                        tl = text.lower()
                        if any(k in tl for k in ('completed', 'task completed', 'finished', 'success', 'succeeded')):
                            success_status = True
                        elif any(k in tl for k in ('failed', 'error', 'unsuccess', 'failed to')):
                            success_status = False
                        else:
                            # 3) 若step_detail内有terminated字段，可作为弱信号
                            terminated = step_detail.get('terminated')
                            if isinstance(terminated, bool):
                                success_status = bool(terminated)
                            else:
                                # 最后回退为 False
                                success_status = False

                # Normalize Python True/False strings
                if isinstance(success_status, str):
                    success_status = success_status.lower() in ('true', '1', 'yes')
                else:
                    success_status = bool(success_status)

            except Exception as e:
                # 若所有策略均失败，记录解析错误并继续（将样本归为 success=False）
                error_samples.append({
                    "sample_index": idx,
                    "error": str(e),
                    "sample": sample
                })
                print(f"警告：样本 {idx} 解析失败 - {str(e)}")

            # 分类存储样本
            if success_status:
                success_true_samples.append(sample)
            else:
                success_false_samples.append(sample)

        except (SyntaxError, ValueError, TypeError) as e:
            # 解析失败的样本记录下来，不中断流程
            error_samples.append({
                "sample_index": idx,
                "error": str(e),
                "sample": sample
            })
            print(f"警告：样本 {idx} 解析失败 - {str(e)}")
        except Exception as e:
            error_samples.append({
                "sample_index": idx,
                "error": str(e),
                "sample": sample
            })
            print(f"警告：样本 {idx} 处理异常 - {str(e)}")

    # 4. 写入success=True的样本
    def write_samples(samples, output_path, label):
        """辅助函数：写入样本并打印统计信息"""
        if not samples:
            print(f"⚠️  无 {label} 样本，跳过写入")
            return
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(samples, f, indent=2, ensure_ascii=False)
            print(f"✅  {label} 样本写入完成：{len(samples)} 个，路径：{os.path.abspath(output_path)}")
        except PermissionError:
            print(f"❌  无权限写入 {label} 样本文件：{output_path}")
        except Exception as e:
            print(f"❌  写入 {label} 样本失败：{str(e)}")

    # 写入两个数据集
    write_samples(success_true_samples, true_output_file, "success=True")
    write_samples(success_false_samples, false_output_file, "success=False")

    # 5. 打印最终统计
    print("\n=== 拆分统计 ===")
    print(f"总样本数：{len(single_round_data)}")
    print(f"success=True 样本数：{len(success_true_samples)}")
    print(f"success=False 样本数：{len(success_false_samples)}")
    print(f"解析失败样本数：{len(error_samples)}")

    # 可选：将解析失败的样本写入文件
    if error_samples:
        error_file = "error_samples.json"
        with open(error_file, 'w', encoding='utf-8') as f:
            json.dump(error_samples, f, indent=2, ensure_ascii=False)
        print(f"⚠️  解析失败的样本已写入：{os.path.abspath(error_file)}")

# ------------------- 脚本使用示例 -------------------
if __name__ == "__main__":
    # 请修改以下路径为实际文件路径
    INPUT_FILE = "/data/EnvScaler/interact_with_env/result/5.single_with_code.json"  # 单轮化后的原始数据集
    TRUE_OUTPUT_FILE = "/data/EnvScaler/interact_with_env/result/6.true_samples.json"  # success=True的数据集
    FALSE_OUTPUT_FILE = "/data/EnvScaler/interact_with_env/result/6.false_samples.json"  # success=False的数据集
    
    # 执行拆分
    split_by_observation_success(INPUT_FILE, TRUE_OUTPUT_FILE, FALSE_OUTPUT_FILE)