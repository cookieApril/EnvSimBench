import json
import ijson
from decimal import Decimal
import traceback

# ===================== 你的文件路径 =====================
DATA_PATH = "/data/EnvScaler/interact_with_env/result/4.single_splited.json"
CODE_PATH = "/data/EnvScaler/interact_with_env/envscaler_env/data/191_env_metadata.json"
OUTPUT_PATH = "/data/EnvScaler/interact_with_env/result/5.single_with_code.json"
# =========================================================

# 自定义JSON编码器：解决 Decimal 无法序列化
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

def main():
    print("正在加载 env 元数据文件...")
    with open(CODE_PATH, "r", encoding="utf-8") as f:
        code_map = json.load(f)

    print("开始流式读取JSON文件...\n")
    valid_data = []
    error_count = 0

    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            for idx, item in enumerate(ijson.items(f, "item"), 1):
                if idx % 100000 == 0:
                    print(f"已解析：{idx:,} 条数据")

                # 核心处理逻辑 + 详细错误捕获
                try:
                    env_id = item["task_info"]["env_id"]
                    if env_id in code_map:
                        item["env_code"] = code_map[env_id]["env_class_code"]
                    valid_data.append(item)

                # 🔥 单条数据出错：打印完整错误上下文
                except Exception as e:
                    error_count += 1
                    print(f"\n❌ 第 {idx} 条数据解析失败！")
                    print(f"错误类型：{type(e).__name__}")
                    print(f"错误信息：{str(e)}")
                    print(f"错误数据片段：{str(item)[:500]}...")  # 打印前500字符
                    print("-" * 80)
                    continue

    except json.JSONDecodeError:
        print("\n⚠️  文件末尾截断，已停止解析，保留所有有效数据")
    except Exception as e:
        print(f"\n⚠️  文件读取异常：{str(e)}")
        traceback.print_exc()

    print(f"\n📊 统计结果：")
    print(f"✅ 有效数据：{len(valid_data)} 条")
    print(f"❌ 异常数据：{error_count} 条")

    # 保存文件 + 序列化错误捕获
    print("\n正在保存文件...")
    try:
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(
                valid_data,
                f,
                ensure_ascii=False,
                indent=4,
                cls=DecimalEncoder
            )
        print(f"\n🎉 保存成功！文件路径：{OUTPUT_PATH}")

    # 🔥 序列化出错：打印具体错误对象
    except Exception as e:
        print(f"\n❌ 文件保存失败！序列化错误：")
        print(f"错误类型：{type(e).__name__}")
        print(f"错误信息：{str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()