<!-- <div align="center">
  <img src="Figs/envsimbench_logo.png" width="150px">
</div> -->
<h1 align="center">EnvSimBench：面向 LLM 环境模拟能力的评估与提升基准</h1>

<div align="center">
  <a href="https://arxiv.org/">
    <img src="https://img.shields.io/badge/Paper-arXiv-b5212f.svg?logo=arxiv" alt="arXiv">
  </a>
  <a href="https://huggingface.co/datasets/Louie-CookieApril/EnvSimBench">
    <img src="https://img.shields.io/badge/Dataset-Hugging%20Face-blue?logo=huggingface" alt="HF Datasets">
  </a>
  <a href="https://huggingface.co/Louie-CookieApril/EnvSimBench-Model">
    <img src="https://img.shields.io/badge/Model-Hugging%20Face-blue?logo=huggingface" alt="HF Models">
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python 3.10+">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
  </a>
</div>

<div align="center">
  <a href="README.md">English</a> | <a href="README_ZH.md">中文</a>
</div>

<h5 align="center">如果我们的工作对你有帮助，欢迎在 GitHub 上点 ⭐ 支持，我们将不胜感激。</h5>

---

## 📑 目录

- [👀 概述](#-概述)
- [✨ 主要贡献](#-主要贡献)
- [📦 数据与模型](#-数据与模型)
- [📊 主要结果](#-主要结果)
- [📁 项目结构](#-项目结构)
- [🚀 快速开始](#-快速开始)
- [🧪 运行评估](#-运行评估)
- [🏋️ 训练你自己的模拟器](#-训练你自己的模拟器)
- [📚 引用](#-引用)
- [📞 联系方式](#-联系方式)

---

## 👀 概述

可扩展的 AI agent 训练依赖于能够忠实模拟动作后果的交互式环境。**人工搭建的环境**构建成本高、可扩展性差、场景多样性受限，难以支撑大规模训练。一个有前景的替代方案是用 **LLM 模拟器**取代可执行环境——但这一范式建立在一个尚未被充分检验的核心假设之上：

> *LLM 真的能够准确地模拟环境反馈吗？*

实际上，LLM 模拟器普遍存在 **幻觉**、**逻辑不一致** 与 **状态静默漂移** 等问题，这些失败会污染 agent 的奖励信号，并抵消该范式本应带来的成本优势。

**EnvSimBench** 是首个专门用于 *评估"模拟器本身"* 而非 agent 的基准。它带来：

- 对 **环境模拟能力（EnvSim Ability）** 的首个形式化定义，使其成为可量化研究目标。
- 一种 **约束驱动的 MDP 建模**：将状态估计与状态转移推理解耦，实现完全程序化、无 LLM 评判的客观评估。
- 一个专门训练的 **4B 模拟器模型**，在 Config Match 指标上超越所有前沿大模型，同时将合成成本降低 90% 以上。

<p align="center">
  <img src="Figs/Fig4.drawio.png" width="95%"><br>
  <em><b>EnvSimBench</b> 总览：轨迹收集 → 三轴分层 → 前沿 LLM 评估 + 专用小模型训练。</em>
</p>

---

## ✨ 主要贡献

1. **形式化定义。** 我们首次将 **环境模拟能力** 形式化为可量化的研究目标，建模为一个完全可观测的状态预测任务：`(s_t, a_t, code(a_t)) → (ô_t, ŝ′_t)`。
2. **基准构建。** 我们构建了 **EnvSimBench**：包含 **167 个多样化环境** 中的 400 条样本，全部带有可程序化校验的标签，并沿 **三个维度（动作结果 / 状态变更复杂度 / 输入参数基数）** 进行细粒度难度分层。
3. **诊断发现。** 对 7 个前沿 LLM 的系统评估揭示出普遍的 **状态变更悬崖（state-change cliff）**：当状态保持不变时所有模型几乎完美，但只要需要同时更新 `|Δ| ≥ 3` 个状态字段就会灾难性下滑。
4. **优化方法。** 我们设计了 **约束驱动的模拟流水线**，配合专用 4B 模型，**降低幻觉**、**提升合成产出 6.8%**、**模拟成本下降 90% 以上**。

<p align="center">
  <img src="Figs/Fig1.drawio.png" width="90%"><br>
  <em>POMDP（左）vs. 约束驱动的 MDP（右）。显式提供 <code>s_t</code> 与 <code>code(a_t)</code> 可从根源消除幻觉、强制逻辑一致性，并通过结构设计避免状态漂移。</em>
</p>

---

## 📦 数据与模型

我们在 Hugging Face 公开了 EnvSimBench 的数据以及训练得到的模拟器模型（SFT + RL）：

| 数据 | 说明 | 链接 |
| --- | --- | --- |
| Benchmark Metadata | 167 个环境上的 400 条评估样本 | [🤗 HuggingFace](https://huggingface.co/datasets/Louie-CookieApril/EnvSimBench/tree/main/Benchmark) |
| SFT Data | 用于训练模拟器的监督微调数据 | [🤗 HuggingFace](https://huggingface.co/datasets/Louie-CookieApril/EnvSimBench/tree/main/SFT%20Data) |
| Process Data | 构建过程中产生的轨迹 / 中间数据 | [🤗 HuggingFace](https://huggingface.co/datasets/Louie-CookieApril/EnvSimBench/tree/main/Process%20Data) |

| 模型 | 说明 | 链接 |
| --- | --- | --- |
| EnvSimBench-Model | 4B 模拟器（SFT + RL），在 Config Match 上超越所有前沿 LLM | [🤗 HuggingFace](https://huggingface.co/Louie-CookieApril/EnvSimBench-Model) |

### 基准样本组成

| 分组 | 子分组 | 样本数 | 约束 |
| --- | --- | --- | --- |
| Failure | `O` 返回错误，`\|Δ\| = 0` | 20 | — |
| No-Change | `\|Δ\| = 0`，动作执行成功 | 80 | 每种参数基数 40 条 |
| Simple | `\|Δ\| ∈ {1, 2}` | 50 | 每个 `\|Δ\|` 取值 25 条 |
| Medium | `\|Δ\| ∈ {3, …, 6}` | 200 | 每个 `\|Δ\|` 取值 50 条 |
| Difficult | `\|Δ\| ∈ {7, …, 12}` | 50 | 跨 `\|Δ\|` 分布 |

每条样本均可基于确定性外部执行器**独立校验**——整个评估流水线 **不使用任何 LLM 评判**。

---

## 📊 主要结果

### 前沿 LLM 普遍存在「状态变更悬崖」

| 模型 | Fail+No-Chg CM | State-Change CM | 总体 CM |
| --- | :---: | :---: | :---: |
| DeepSeek-V3.2 | 100% | 10.0% | 32.5% |
| Qwen3.5-397B-A17B | 100% | 23.0% | 42.3% |
| GPT-5.4 | 100% | 22.7% | 42.0% |
| Gemini-3.1-Pro-Preview | 100% | 22.7% | 42.0% |
| Claude-Sonnet-4.6 | 99% | 17.3% | 37.8% |
| MiniMax-M2.7 | 99% | 22.7% | 41.8% |
| GLM-5 | 100% | 21.3% | 41.0% |
| **本文 (Full-Balance2, 4B)** | **100%** | **—** | **45.3%** |

- 所有前沿模型在「状态保持不变」的样本上 CM ≥ 99%，但在需要更新状态的样本上明显坍塌。
- 当 `|Δ| ≥ 5` 时，所有前沿模型的 CM 几乎归零。
- 我们的 **4B 专用模拟器在 Config Match 上超越所有前沿 LLM**，参数规模约为前者的 1/59。

<p align="center">
  <img src="Figs/state_change_cliff.png" width="92%"><br>
  <em>Config Match 与 <code>|Δ|</code> 的关系：前沿 LLM（细线）在 <code>|Δ| ≥ 3</code> 时急剧下降；本文的 Full-Balance2（粗线）在可部署区间领先最高 +10pp。</em>
</p>

### 下游合成产出验证

将我们的 4B 模拟器替换 EnvScaler 合成流水线中的大模型集成后：

- 通过 0.85 质量阈值的环境数从 191 提升到 204，**合成产出 +6.8%**
- **模拟成本下降 90% 以上**
- 在成本与质量两个维度上达到帕累托最优

---

## 📁 项目结构

```
EnvSimBench/
├── Benchmark/                 # 400 条评估样本及执行器标签
├── Construction/              # 轨迹收集与三轴分层流水线
├── Evaluation/                # 前沿 LLM 评估脚本（FM / CM 指标）
├── EnvScaler/                 # 下游合成流水线集成 / SFT 数据准备
├── Figs/                      # 论文 / README 中使用的图
└── requirements.txt
```

> 💡 各子目录均附有详细的 `README.md` 说明。

---

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/cookieApril/EnvSimBench
cd EnvSimBench
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

> 训练流程依赖 **[LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory)**。请按其官方指引安装 `llamafactory-cli` 与配套的 `vllm` 运行时。

### 3. 配置 LLM 推理服务

#### 方式 A —— 使用云端 API

```bash
# .env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
```

#### 方式 B —— 使用 LLaMA-Factory + vLLM 自建 EnvSimBench-Model 服务

```bash
DISABLE_VERSION_CHECK=1 llamafactory-cli api \
  --model_name_or_path saves/qwen3-4b-Base-noreasoning-selectedByTaskid-Change-balance2 \
  --template qwen \
  --infer_backend vllm \
  --vllm_maxlen 16384 \
  --vllm_gpu_util 0.9 \
  --vllm_enforce_eager \
  --no_enable_thinking
```

服务暴露 OpenAI 兼容的 `/v1/chat/completions` 接口。如果要从其他机器访问，请把 `OPENAI_BASE_URL` 指向 GPU 节点的 IP（在 GPU 节点上执行 `ip a`，取 `bond0` 中的地址）：

```bash
export OPENAI_API_KEY="dummy"
export OPENAI_BASE_URL="http://<GPU_NODE_IP>:8013/v1"
export PORT=8013
```

简单连通性测试：

```bash
python -c "
import requests
resp = requests.post(
    f'{__import__(\"os\").environ[\"OPENAI_BASE_URL\"]}/chat/completions',
    json={
        'model': 'models/Qwen/Qwen3-4B-Base',
        'messages': [{'role': 'user', 'content': '你好，请介绍一下你自己。'}],
        'max_tokens': 100,
    },
)
print(resp.json()['choices'][0]['message']['content'])
"
```

### 4. 下载基准数据

```bash
huggingface-cli download Louie-CookieApril/EnvSimBench \
    --repo-type dataset --local-dir ./data
```

---

## 🧪 运行评估

使用 `Evaluation/` 下的脚本，在约束驱动的 MDP 框架下评估任意模型：

```bash
cd Evaluation
python evaluate.py \
  --input ./eval/9.choice_final_combined-167env.json \
  --model qwen3_4B \
  --max_samples 400 \
  --max_workers 3
```

参数说明：

| 参数 | 说明 |
| --- | --- |
| `--input` | 基准 JSON 路径（如 `9.choice_final_combined-167env.json`，400 样本 / 167 环境）。 |
| `--model` | 模型标识——可以是托管 API 名称（如 `gpt-4o`、`deepseek-v3.2`），也可以是映射到本地服务的 key（如 `qwen3_4B`）。 |
| `--max_samples` | 最多评估的样本数（跑全集请填 `400`）。 |
| `--max_workers` | 推理并发请求数。 |

每条 prompt 实例化 `(s_t, a_t, code(a_t))`，并使用两个**纯程序化的二值指标**打分：

- **Feedback Match (FM)**：预测观测 `ô_t` 与真值 `o_t` 是否完全一致。
- **Config Match (CM)**：将预测的 Δ 操作应用到 `s_t` 后是否完全得到 `s′_t`。CM 不受输出格式约定影响，是跨模型对比时的主要推理指标。

按维度（Failure / No-Change / Simple / Medium / Difficult，以及每个 `|Δ|` 取值）的细分结果会写入与输入 JSON 同目录下。

---

## 🏋️ 训练你自己的模拟器

我们公开了 SFT 数据以及训练 4B 模型所用的 **Balance2** 数据组合。训练基于 **LLaMA-Factory**，采用全参数 SFT + DeepSpeed ZeRO-3，硬件为 2× A800 (80 GB)。

### 1. 拉取 SFT 数据

```bash
huggingface-cli download Louie-CookieApril/EnvSimBench \
    --repo-type dataset --local-dir ./data
```

并在 LLaMA-Factory 的 `data/dataset_info.json` 中以 `13.SFT-data-noreasoning-selectedByTaskid-Change-balance2` 为 key 注册数据集。

### 2. 全参数 SFT

```bash
# NCCL / 多卡环境变量
export NCCL_P2P_DISABLE=1
export NCCL_IB_DISABLE=1   # 没有 IB 网卡建议关掉
export CUDA_VISIBLE_DEVICES=0,1

FORCE_TORCHRUN=1 NPROC_PER_NODE=2 DISABLE_VERSION_CHECK=1 llamafactory-cli train \
  --model_name_or_path models/Qwen/Qwen3-4B-Base \
  --template qwen \
  --dataset 13.SFT-data-noreasoning-selectedByTaskid-Change-balance2 \
  --dataset_dir data \
  --finetuning_type full \
  --output_dir saves/qwen3-4b-Base-noreasoning-selectedByTaskid-Change-balance2 \
  --per_device_train_batch_size 1 \
  --gradient_accumulation_steps 16 \
  --learning_rate 2e-5 \
  --num_train_epochs 3 \
  --bf16 \
  --overwrite_output_dir \
  --ddp_find_unused_parameters false \
  --cutoff_len 8192 \
  --do_train \
  --save_strategy steps \
  --save_steps 200 \
  --save_total_limit 3 \
  --ddp_timeout 18000 \
  --flash_attn fa2 \
  --gradient_checkpointing true \
  --lr_scheduler_type cosine \
  --warmup_ratio 0.05 \
  --logging_steps 10 \
  --deepspeed ds_z3_config.json
```

### 3. 部署训练好的 checkpoint

```bash
DISABLE_VERSION_CHECK=1 llamafactory-cli api \
  --model_name_or_path saves/qwen3-4b-Base-noreasoning-selectedByTaskid-Change-balance2 \
  --template qwen \
  --infer_backend vllm \
  --vllm_maxlen 16384 \
  --vllm_gpu_util 0.9 \
  --vllm_enforce_eager \
  --no_enable_thinking
```

### 4. 评估

```bash
cd Evaluation
python evaluate.py \
  --input ./eval/9.choice_final_combined-167env.json \
  --model qwen3_4B \
  --max_samples 400 \
  --max_workers 3
```

> **数据组合比数据规模更重要。** 按源环境中 `|Δ|` 的真实分布构造（1K Failure + 1K No-Change + 2K Simple-Change + 2.23K Complex-Change ≈ 6.23K）显著优于在 5K 数据规模下的简单堆量。

---

## 📚 引用

如果我们的工作对你有帮助，欢迎引用，我们将不胜感激。

```bibtex
@article{liu2025envsimbench,
  title   = {EnvSimBench: A Benchmark for Evaluating and Improving LLM-Based Environment Simulation},
  author  = {Liu, Yi and Hui, TingFeng and Zhang, Wei and Sun, Li and Su, Ningxin and Wang, Jian and Su, Sen},
  journal = {arXiv preprint},
  year    = {2025}
}
```

---

## 📞 联系方式

如有任何问题、建议或合作意向，欢迎联系我们：

- **Yi Liu** — [louie@bupt.edu.cn](mailto:louie@bupt.edu.cn)
- 也可在本仓库提 Issue。
