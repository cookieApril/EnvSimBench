#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON文件拼接脚本：将第二个JSON文件的内容直接拼接在第一个文件内容之后
使用方法：
1. 修改下方的 INPUT_FILE1、INPUT_FILE2、OUTPUT_FILE 为实际文件路径
2. 运行脚本：python json_concat.py
"""

import os

# ====================== 配置区（请修改为你的文件路径）======================
# 第一个JSON文件（拼接在前）
INPUT_FILE1 = "/data/EnvScaler/interact_with_env/result/1.tra_3070sample.json"
# 第二个JSON文件（拼接在后）
INPUT_FILE2 = "/data/EnvScaler/interact_with_env/result/envscaler_non_conversation_sft/gpt-5-mini-fc_2026-03-23-18-29-39.json"
# 拼接后的输出文件
OUTPUT_FILE = "/data/EnvScaler/interact_with_env/result/1.tra_3462sample.json"
# ==========================================================================

def concat_json_files(file1: str, file2: str, output_file: str) -> None:
    """
    拼接两个JSON文件的内容（文本层面直接拼接）
    :param file1: 第一个输入文件路径
    :param file2: 第二个输入文件路径
    :param output_file: 输出文件路径
    """
    try:
        # 检查输入文件是否存在
        if not os.path.exists(file1):
            raise FileNotFoundError(f"第一个文件不存在：{file1}")
        if not os.path.exists(file2):
            raise FileNotFoundError(f"第二个文件不存在：{file2}")

        # 读取第一个文件内容
        with open(file1, "r", encoding="utf-8") as f1:
            content1 = f1.read().strip()  # strip() 去除文件末尾的空白/换行，避免多余空行

        # 读取第二个文件内容
        with open(file2, "r", encoding="utf-8") as f2:
            content2 = f2.read().strip()

        # 拼接内容（直接拼接，中间加一个换行分隔，更易读）
        combined_content = content1 + "\n" + content2

        # 写入输出文件
        with open(output_file, "w", encoding="utf-8") as f_out:
            f_out.write(combined_content)

        print(f"✅ 拼接成功！")
        print(f"📄 输入文件1：{file1}")
        print(f"📄 输入文件2：{file2}")
        print(f"📤 输出文件：{output_file}")
        print(f"📊 拼接后文件大小：{os.path.getsize(output_file)} 字节")

    except FileNotFoundError as e:
        print(f"❌ 错误：{e}")
    except PermissionError:
        print(f"❌ 错误：没有文件读写权限，请检查文件是否被占用或路径权限")
    except Exception as e:
        print(f"❌ 未知错误：{e}")

if __name__ == "__main__":
    # 执行拼接函数
    concat_json_files(INPUT_FILE1, INPUT_FILE2, OUTPUT_FILE)