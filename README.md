<!-- <div align="center">
  <img src="Figs/envsimbench_logo.png" width="150px">
</div> -->
<h1 align="center">EnvSimBench: A Benchmark for Evaluating and Improving LLM-Based Environment Simulation</h1>

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

<h5 align="center">If you find our work helpful, please give us a star ⭐ on GitHub. We greatly appreciate your support.</h5>

---

## 📑 Contents

- [👀 Overview](#-overview)
- [✨ Key Contributions](#-key-contributions)
- [📊 Main Results](#-main-results)
- [📦 Dataset & Models](#-dataset--models)
- [📁 Project Structure](#-project-structure)
- [🚀 Quick Start](#-quick-start)
- [🧪 Running the Benchmark](#-running-the-benchmark)
- [🏋️ Training Your Own Simulator](#-training-your-own-simulator)
- [📚 Citation](#-citation)
- [📞 Contact](#-contact)

---

## 👀 Overview

Scalable AI agent training relies on interactive environments that faithfully simulate the consequences of agent actions. Manually crafted environments are expensive to build, brittle to extend, and limited in diversity. A promising alternative is to replace executable environments with **LLM-simulated** counterparts — but this paradigm rests on an unexamined assumption:

> *Can LLMs accurately simulate environmental feedback?*

In practice, LLM simulators suffer from **hallucinations**, **logical inconsistencies**, and **silent state drift** — failures that corrupt agent reward signals and erode the cost advantage that motivated the paradigm.

**EnvSimBench** is the first rigorous benchmark designed to *evaluate the simulator itself*, rather than the agent. It introduces:

- A formal definition of **Environment Simulation Ability (EnvSim Ability)** as a measurable capability.
- A **constraint-driven MDP formulation** that decouples state estimation from transition reasoning, enabling LLM-free, programmatic evaluation.
- A specialized **4B simulation model** that surpasses frontier LLMs on Config Match while cutting synthesis costs by over 90%.

<p align="center">
  <img src="Figs/Fig3.png" width="95%" alt="Overview of EnvSimBench"><br>
  <em><b>Overview of EnvSimBench.</b> Module A collects multi-turn trajectories from EnvScaler environments and converts them into self-contained state-prediction samples. Module B uses executor-verified labels and three-axis stratification to build a benchmark of 400 samples across 167 environments. Module C evaluates seven frontier LLMs and trains a specialized 4B simulator for downstream environment synthesis.</em>
</p>

---

## ✨ Key Contributions

1. **Formalization.** We provide the first formal definition and operationalization of **Environment Simulation Ability** as a quantifiable research objective, framed as fully-observable state prediction over `(s_t, a_t, code(a_t)) → (ô_t, ŝ′_t)`.
2. **Benchmark.** We construct **EnvSimBench**: 400 samples drawn from **167 diverse environments**, equipped with verifiable programmatic labels and **three-axis difficulty stratification** (action outcome, state-change complexity, argument cardinality).
3. **Diagnosis.** Systematic evaluation of seven frontier LLMs reveals a universal **state-change cliff**: every model is near-perfect when state is invariant, yet collapses catastrophically once `|Δ| ≥ 3` simultaneous state updates are required.
4. **Optimization.** We design a **constraint-driven simulation pipeline** that, paired with a specialized 4B model, **reduces hallucination**, **boosts synthesis yield by 6.8%**, and **cuts simulation cost by over 90%**.

<p align="center">
  <img src="Figs/Fig1.drawio.png" width="90%"><br>
  <em>POMDP (left) vs. constraint-driven MDP (right). Supplying <code>s_t</code> and <code>code(a_t)</code> explicitly removes hallucination, enforces logical consistency, and prevents state drift by construction.</em>
</p>

---
## 📊 Main Results

### Frontier LLMs Exhibit a Universal State-Change Cliff

EnvSimBench reveals a pronounced **state-change cliff**. The seven evaluated frontier LLMs achieve **99–100% Config Match (CM)** on state-preserving samples, but their ability to predict state transitions drops sharply when an action must update multiple fields. Meanwhile, Feedback Match (FM) can remain high even when the predicted environment state is incorrect, revealing a potentially silent source of corrupted training signals.

<p align="center">
  <img src="Figs/Figure5_LargeText.png" width="95%" alt="Frontier LLM performance across EnvSimBench difficulty groups"><br>
  <em><b>Frontier LLM performance across difficulty groups.</b> Blue bars show Feedback Match and orange bars show Config Match under non-thinking inference. Models perform reliably on Failure and No-Change samples, but CM drops substantially on Simple, Medium, and Difficult state-changing operations. Qwen3.5-397B-A17B achieves the highest overall CM among frontier models (42.3%), while GLM-5 achieves the highest overall FM (80.5%).</em>
</p>

| Model | Fail+No-Chg CM | State-Change CM | Overall CM |
| --- | :---: | :---: | :---: |
| DeepSeek-V3.2 | 100.0% | 10.0% | 32.5% |
| Qwen3.5-397B-A17B | 100.0% | **23.0%** | **42.3%** |
| GPT-5.4 | 100.0% | 22.7% | 42.0% |
| Gemini-3.1-Pro-Preview | 100.0% | 22.7% | 42.0% |
| Claude-Sonnet-4.6 | 99.0% | 17.3% | 37.8% |
| MiniMax-M2.7 | 99.0% | 22.7% | 41.8% |
| GLM-5 | 100.0% | 21.3% | 41.0% |
| **Ours (Full-Balance2, 4B)** | **99.0%** | **27.3%** | **45.3%** |

The results expose three consistent patterns:

- Every frontier model achieves at least **99% CM** on state-preserving operations, but only **10.0–23.0% CM** on state-changing operations.
- At `|Δ| = 5`, all evaluated frontier models fall to **4% CM or lower**, marking the sharpest point of the state-change cliff.
- High FM does not necessarily imply a correct state transition: a model can return plausible feedback while silently corrupting the underlying environment state.

### A Specialized 4B Simulator Outperforms Frontier LLMs

Guided by the benchmark findings, we train **Full-Balance2**, a specialized 4B simulator whose training mixture covers failure, no-change, simple-change, and complex-change operations. Full-Balance2 achieves **45.3% overall CM**, exceeding the strongest frontier baseline by **3.0 percentage points**, while reaching **79.5% overall FM**.

Its advantage is concentrated in the practically relevant low-to-medium complexity regime. For transitions involving one to four changed fields, Full-Balance2 exceeds the strongest frontier result at each state-change level by up to **10 percentage points**. Transitions requiring five or more changes remain challenging for both specialized and frontier models.

<p align="center">
  <img src="Figs/Fig_SFT_vs_Frontier.png" width="85%" alt="Full-Balance2 compared with frontier LLMs by state-change count"><br>
  <em><b>Config Match by state-change count.</b> Full-Balance2 is compared with seven frontier LLMs under the same benchmark setting. The specialized 4B model leads at every level from one to four changed fields, with gains of up to 10 percentage points. The final point pools samples with seven to twelve changed fields.</em>
</p>

### Downstream Environment Synthesis

We further replace EnvScaler's large-model simulation ensemble with Full-Balance2. Under the same 0.85 quality threshold, the specialized simulator improves both synthesis quality and efficiency:

- **+6.8% synthesis yield**, increasing the number of passing environments from 191 to 204.
- **More than 90% lower simulation cost.**
- Approximately **59× fewer model parameters** than the frontier-model pipeline.

These results show that EnvSimBench provides both a diagnostic framework for identifying simulation failures and a practical path toward more accurate and cost-efficient environment synthesis.

---

## 📦 Dataset & Models

We release the EnvSimBench data and our Full-Balance2 4B simulator, trained with full-parameter SFT, on Hugging Face:

| Data | Description | Link |
| --- | --- | --- |
| Benchmark Metadata | 400 evaluation samples across 167 environments | [🤗 HuggingFace](https://huggingface.co/datasets/Louie-CookieApril/EnvSimBench/tree/main/Benchmark) |
| SFT Data | Supervised fine-tuning data for the simulator | [🤗 HuggingFace](https://huggingface.co/datasets/Louie-CookieApril/EnvSimBench/tree/main/SFT%20Data) |
| Process Data | Process / trajectory data used during construction | [🤗 HuggingFace](https://huggingface.co/datasets/Louie-CookieApril/EnvSimBench/tree/main/Process%20Data) |

| Model | Description | Link |
| --- | --- | --- |
| EnvSimBench-Model | Full-Balance2 4B simulator trained with full-parameter SFT — surpasses frontier LLMs on Config Match | [🤗 HuggingFace](https://huggingface.co/Louie-CookieApril/EnvSimBench-Model) |

### Benchmark Composition

| Group | Subgroup | Samples | Constraint |
| --- | --- | --- | --- |
| Failure | `O` returns error, `\|Δ\| = 0` | 20 | — |
| No-Change | `\|Δ\| = 0`, action succeeds | 80 | 40 per argument cardinality |
| Simple | `\|Δ\| ∈ {1, 2}` | 50 | 25 per `\|Δ\|` value |
| Medium | `\|Δ\| ∈ {3, …, 6}` | 200 | 50 per `\|Δ\|` value |
| Difficult | `\|Δ\| ∈ {7, …, 12}` | 50 | Distributed across `\|Δ\|` |

Each sample is **independently verifiable** against a deterministic external executor — no LLM-as-judge anywhere in the pipeline.

---

## 📁 Project Structure

```
EnvSimBench/
├── Benchmark/                 # 400 evaluation samples + executor labels
├── Construction/              # Trajectory collection & three-axis stratification pipeline
├── Evaluation/                # Frontier LLM evaluation harness (FM / CM metrics)
├── EnvScaler/                 # Downstream synthesis-pipeline integration (SFT data prep)
├── Figs/                      # Figures used in the paper / README
└── requirements.txt
```

> 💡 Each subdirectory ships its own `README.md` with detailed usage instructions.

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/cookieApril/EnvSimBench
cd EnvSimBench
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> Training relies on **[LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory)**. Please follow its official installation guide to set up `llamafactory-cli` and the matching `vllm` runtime before running the training/serving scripts below.

### 3. Configure your LLM service

#### Option A — Use a hosted API

```bash
# .env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
```

#### Option B — Self-host the EnvSimBench-Model with LLaMA-Factory + vLLM

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

The service exposes an OpenAI-compatible `/v1/chat/completions` endpoint. To call it from another machine, point `OPENAI_BASE_URL` at the GPU node's IP (find it via `ip a` → `bond0`):

```bash
export OPENAI_API_KEY="dummy"
export OPENAI_BASE_URL="http://<GPU_NODE_IP>:8013/v1"
export PORT=8013
```

A quick sanity check:

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

### 4. Download the benchmark

```bash
huggingface-cli download Louie-CookieApril/EnvSimBench \
    --repo-type dataset --local-dir ./data
```

---

## 🧪 Running the Benchmark

Evaluate any model under the constraint-driven MDP formulation using the script in `Evaluation/`:

```bash
cd Evaluation
python evaluate.py \
  --input ./eval/9.choice_final_combined-167env.json \
  --model qwen3_4B \
  --max_samples 400 \
  --max_workers 3
```

Arguments:

| Flag | Description |
| --- | --- |
| `--input` | Path to the benchmark JSON (e.g. `9.choice_final_combined-167env.json`, 400 samples / 167 envs). |
| `--model` | Model identifier — either a hosted API name (`gpt-4o`, `deepseek-v3.2`, …) or a local key like `qwen3_4B` that maps to your self-hosted endpoint. |
| `--max_samples` | Cap on samples to evaluate (use `400` for the full benchmark). |
| `--max_workers` | Concurrency for inference requests. |

Each prompt instantiates `(s_t, a_t, code(a_t))` and is scored by two **binary, programmatic** metrics:

- **Feedback Match (FM)** — exact equality between predicted observation `ô_t` and ground-truth `o_t`.
- **Config Match (CM)** — whether predicted Δ-operations, applied to `s_t`, reproduce `s′_t` exactly. CM is invariant to output-format conventions and is the primary cross-model reasoning metric.

Per-axis breakdowns (Failure / No-Change / Simple / Medium / Difficult, plus per-`|Δ|` slices) are written next to the input JSON.

---

## 🏋️ Training Your Own Simulator

We release the SFT data and the **Balance2** mixture used to train our 4B model. Training is implemented on top of **LLaMA-Factory** with full-parameter SFT + DeepSpeed ZeRO-3 on 2× A800 (80 GB) GPUs.

### 1. Fetch the SFT data

```bash
huggingface-cli download Louie-CookieApril/EnvSimBench \
    --repo-type dataset --local-dir ./data
```

Register the dataset in your LLaMA-Factory `data/dataset_info.json` under the key `13.SFT-data-noreasoning-selectedByTaskid-Change-balance2`.

### 2. Run full-parameter SFT

```bash
# NCCL / multi-GPU setup
export NCCL_P2P_DISABLE=1
export NCCL_IB_DISABLE=1   # disable if no IB NIC
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

### 3. Serve the trained checkpoint

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

### 4. Evaluate

```bash
cd Evaluation
python evaluate.py \
  --input ./eval/9.choice_final_combined-167env.json \
  --model qwen3_4B \
  --max_samples 400 \
  --max_workers 3
```

> **Composition matters more than volume.** Mirroring the empirical `|Δ|` distribution of source environments (1 K failure + 1 K no-change + 2 K simple-change + 2.23 K complex-change ≈ 6.23 K total) outperforms naïve scaling at the 5 K-sample regime.

