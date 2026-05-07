import json
import os
import ijson
from decimal import Decimal  # 【改动1】导入Decimal类型

# 【改动2】自定义JSON编码器，处理Decimal类型
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        # 处理Decimal类型：转成字符串（推荐，保留精度）或浮点数（根据需求选）
        if isinstance(obj, Decimal):
            # 方案1：转字符串（推荐，避免精度丢失）
            return str(obj)
            # 方案2：转浮点数（如果不需要高精度，仅需数值）
            # return float(obj)
        # 处理其他可能的非序列化类型（可选，预防后续报错）
        elif isinstance(obj, (int, float, str, list, dict, bool, type(None))):
            return super().default(obj)
        else:
            # 其他未知类型转字符串，避免脚本中断
            print(f"警告：发现未知类型 {type(obj)}，已转为字符串")
            return str(obj)

def read_large_json_array_ijson(file_path: str):
    """
    用ijson流式解析超大JSON数组（支持单行/多行JSON），逐对象返回，效率极高
    :param file_path: 超大JSON数组文件路径
    :return: 逐个返回样本字典
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # 流式解析JSON数组中的每个元素（item是数组内的单个样本）
            print("开始流式解析JSON数组（ijson）...")
            # ijson.items(文件句柄, "item") 专门解析JSON数组的每个元素
            for idx, sample in enumerate(ijson.items(f, "item"), 1):
                if idx % 10 == 0:
                    print(f"已解析 {idx} 个样本（ijson流式解析）")
                yield sample
            print(f"JSON解析完成，共解析 {idx if 'idx' in locals() else 0} 个样本")
    except Exception as e:
        print(f"ijson解析JSON失败: {e}")
        raise

def group_samples_by_change_count_streaming(json_file: str, output_prefix: str = "/data/EnvScaler/interact_with_env/result/class/7.true_samples_change_count"):
    """
    流式读取 JSON 文件，按 change_count 分组，并实时写入对应的 JSON 文件。
    """
    # 确保输出目录存在
    output_dir = os.path.dirname(output_prefix)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"创建/确认输出目录: {output_dir}")
    
    # 存储每个 change_count 对应的文件句柄和是否已写入第一个元素
    file_handles = {}          
    first_element_written = {} 

    try:
        sample_count = 0
        # 改用ijson的解析函数（核心改动）
        for sample in read_large_json_array_ijson(json_file):
            sample_count += 1
            
            # 提取 change_count
            try:
                change_count = sample.get("step_detail", {}).get("config_change", {}).get("change_count")
                if change_count is None:
                    print(f"\n警告：样本 {sample_count} 缺少 change_count，跳过。样本 ID: {sample.get('task_info', {}).get('task_id', '未知')}")
                    continue
                change_count = str(change_count)
            except Exception as e:
                print(f"\n解析样本 {sample_count} 的 change_count 失败: {e}")
                continue

            # 创建/打开对应change_count的文件
            if change_count not in file_handles:
                filename = f"{output_prefix}_{change_count}.json"
                f = open(filename, 'w', encoding='utf-8')
                f.write('[\n')
                file_handles[change_count] = f
                first_element_written[change_count] = False
                print(f"\n创建文件并开始写入: {filename}")

            f = file_handles[change_count]

            # 写入样本（处理逗号分隔）
            if first_element_written[change_count]:
                f.write(',\n')
            else:
                first_element_written[change_count] = True

            # 【改动3】使用自定义编码器处理Decimal类型
            json.dump(sample, f, ensure_ascii=False, indent=2, cls=DecimalEncoder)
            f.flush()
            os.fsync(f.fileno())  # 强制刷盘到文件

            # 每处理50个样本打印一次总进度
            if sample_count % 50 == 0:
                print(f"总处理进度：已处理 {sample_count} 个样本，已创建 {len(file_handles)} 个分组文件")

        print(f"\n✅ 处理完成！共处理 {sample_count} 个样本，生成 {len(file_handles)} 个分组文件")

    except Exception as e:
        print(f"\n❌ 处理样本时发生错误: {e}")
        raise
    finally:
        # 关闭所有文件并补全JSON数组结尾
        for change_count, f in file_handles.items():
            try:
                f.write('\n]')
                f.flush()
                os.fsync(f.fileno())
                f.close()
                print(f"✅ 已完成文件写入并关闭: {output_prefix}_{change_count}.json")
            except Exception as e:
                print(f"❌ 关闭文件 {change_count} 时出错: {e}")


if __name__ == "__main__":
    input_file = "/data/EnvScaler/interact_with_env/result/9.choice_final_combined.json"
    print(f"🚀 开始处理超大JSON文件: {input_file}")
    # 检查文件是否存在
    if not os.path.exists(input_file):
        print(f"❌ 错误：输入文件不存在 → {input_file}")
    else:
        # 检查文件大小（确认是超大文件）
        file_size = os.path.getsize(input_file) / (1024*1024)  # 转为MB
        print(f"📄 文件大小：{file_size:.2f} MB")
        group_samples_by_change_count_streaming(input_file)