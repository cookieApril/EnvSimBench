# 1. 开启 Debug 日志，放宽网卡匹配
是输入export NCCL_SOCKET_IFNAME=bond0
export NCCL_IB_DISABLE=1
export NCCL_P2P_LEVEL=NVL
export CUDA_VISIBLE_DEVICES=0,1

# # 2. 挂载分布式启动器，安全续训 4B 模型

FORCE_TORCHRUN=1 NPROC_PER_NODE=2 DISABLE_VERSION_CHECK=1 llamafactory-cli train \
  --model_name_or_path models/Qwen/Qwen3-4B-Base \
  --template qwen \
  --dataset 13.sft_data_alpaca_en \
  --dataset_dir data \
  --finetuning_type lora \
  --lora_rank 16 \
  --lora_alpha 32 \
  --lora_dropout 0.05 \
   --output_dir saves/qwen3-4b-Base-lora-v1-multi \
  --per_device_train_batch_size 2 \
  --gradient_accumulation_steps 8 \
  --learning_rate 2e-4 \
  --num_train_epochs 3 \
  --bf16 \
  --overwrite_output_dir \
  --ddp_find_unused_parameters false \
  --cutoff_len 8192 \
  --do_train \
  --save_strategy steps \
  --save_steps 200 \
  --save_total_limit 3 \
  --flash_attn fa2 \
  --ddp_timeout 18000 \
  --resume_from_checkpoint saves/qwen3-4b-Base-lora-v1-multi/checkpoint-1400
