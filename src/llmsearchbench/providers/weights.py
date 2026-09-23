"""Where each catalogued model's weights actually live.

Exact Hugging Face repos, checked by hand. Absence from this map means
"not checked", which every consumer reports honestly rather than guessing —
the map decides both what the coverage page calls open-weight and what the
size-against-accuracy chart can plot.
"""

from __future__ import annotations

#: OpenRouter (or provider) model id -> Hugging Face repo.
WEIGHTS = {
    "openai/gpt-oss-20b": "openai/gpt-oss-20b",
    "openai/gpt-oss-120b": "openai/gpt-oss-120b",
    "openai/gpt-oss-safeguard-20b": "openai/gpt-oss-safeguard-20b",
    "z-ai/glm-4.7": "zai-org/GLM-4.7",
    "z-ai/glm-4.7-flash": "zai-org/GLM-4.7-Flash",
    "z-ai/glm-5": "zai-org/GLM-5",
    "z-ai/glm-5.2": "zai-org/GLM-5.2",
    "z-ai/glm-5.3": "zai-org/GLM-5.3",
    "z-ai/glm-5.3-flash": "zai-org/GLM-5.3-Flash",
    "z-ai/glm-4.5": "zai-org/GLM-4.5",
    "z-ai/glm-4.5-air": "zai-org/GLM-4.5-Air",
    "z-ai/glm-4.6": "zai-org/GLM-4.6",
    "deepseek/deepseek-r1": "deepseek-ai/DeepSeek-R1",
    "deepseek/deepseek-v3.2": "deepseek-ai/DeepSeek-V3.2",
    "deepseek/deepseek-v4-flash": "deepseek-ai/DeepSeek-V4-Flash",
    "deepseek/deepseek-v4-pro": "deepseek-ai/DeepSeek-V4-Pro",
    "deepseek/deepseek-v4.1-flash": "deepseek-ai/DeepSeek-V4.1-Flash",
    "nvidia/nemotron-3-nano-30b-a3b": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16",
    "nvidia/nemotron-3-super-120b-a12b": "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16",
    "nvidia/nemotron-3-ultra-550b-a55b": "nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16",
    "nvidia/nemotron-3.5-lightning": "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16",
    "thinkingmachines/inkling": "thinkingmachines/Inkling",
    "thinkingmachines/inkling-small": "thinkingmachines/Inkling-Small",
    "moonshotai/kimi-k2": "moonshotai/Kimi-K2-Instruct",
    "moonshotai/kimi-k2.5": "moonshotai/Kimi-K2.5",
    "moonshotai/kimi-k2.6": "moonshotai/Kimi-K2.6",
    "moonshotai/kimi-k2.7-code": "moonshotai/Kimi-K2.7-Code",
    "moonshotai/kimi-k3": "moonshotai/Kimi-K3",
    "minimax/minimax-m2": "MiniMaxAI/MiniMax-M2",
    "minimax/minimax-m2.5": "MiniMaxAI/MiniMax-M2.5",
    "minimax/minimax-m2.7": "MiniMaxAI/MiniMax-M2.7",
    "minimax/minimax-m3": "MiniMaxAI/MiniMax-M3",
    "minimax/minimax-m1": "MiniMaxAI/MiniMax-M1-80k",
    "xiaomi/mimo-v2.5": "XiaomiMiMo/MiMo-V2.5",
    "xiaomi/mimo-v2.5-pro": "XiaomiMiMo/MiMo-V2.5-Pro",
    "xiaomi/mimo-v2.6-flash": "XiaomiMiMo/MiMo-V2.6-Flash",
    "xiaomi/mimo-v2.6-pro": "XiaomiMiMo/MiMo-V2.6-Pro",
    "meta-llama/llama-3.1-8b-instruct": "meta-llama/Llama-3.1-8B-Instruct",
    "meta-llama/llama-3.1-70b-instruct": "meta-llama/Llama-3.1-70B-Instruct",
    "meta-llama/llama-3.3-70b-instruct": "meta-llama/Llama-3.3-70B-Instruct",
    "meta-llama/llama-4-scout": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
    "meta-llama/llama-4-maverick": "meta-llama/Llama-4-Maverick-17B-128E-Instruct",
    "meta/muse-glimmer-30b": "facebook/Muse-Glimmer-30B",
    "mistralai/mistral-nemo": "mistralai/Mistral-Nemo-Instruct-2407",
    "mistralai/mistral-small-3.2-24b-instruct": (
        "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
    ),
    "mistralai/mistral-small-3.1-24b-instruct": (
        "mistralai/Mistral-Small-3.1-24B-Instruct-2503"
    ),
    "mistralai/mixtral-8x22b-instruct": "mistralai/Mixtral-8x22B-Instruct-v0.1",
    "mistralai/mistral-small-2603": "mistralai/Mistral-Small-2603",
    "mistralai/ministral-8b-2512": "mistralai/Ministral-8B-Instruct-2512",
    "mistralai/ministral-14b-2512": "mistralai/Ministral-14B-Instruct-2512",
    "mistralai/ministral-3b-2512": "mistralai/Ministral-3B-Instruct-2512",
    "mistralai/devstral-2512": "mistralai/Devstral-2512",
    "meituan/longcat-2.0": "meituan-longcat/LongCat-2.0",
    "tencent/hy3": "tencent/HY3",
    "tencent/hy4-preview": "tencent/HY4",
    "tencent/hunyuan-a13b-instruct": "tencent/Hunyuan-A13B-Instruct",
    "dots-studio/dots-3-note-preview": "rednote-hilab/dots3-note",
    "sakana/fugu-max": "SakanaAI/Fugu-Max",
    "sakana/sakana-namazu": "SakanaAI/Namazu",
    # Qwen, verified against the Hugging Face API on 2026-09-23.
    "qwen/qwen-2.5-7b-instruct": "Qwen/Qwen2.5-7B-Instruct",
    "qwen/qwen-2.5-72b-instruct": "Qwen/Qwen2.5-72B-Instruct",
    "qwen/qwen3-8b": "Qwen/Qwen3-8B",
    "qwen/qwen3-32b": "Qwen/Qwen3-32B",
    "qwen/qwen3-30b-a3b-instruct-2507": "Qwen/Qwen3-30B-A3B-Instruct-2507",
    "qwen/qwen3-30b-a3b-thinking-2507": "Qwen/Qwen3-30B-A3B-Thinking-2507",
    "qwen/qwen3-coder-30b-a3b-instruct": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
    "qwen/qwen3-235b-a22b-2507": "Qwen/Qwen3-235B-A22B-Instruct-2507",
    "qwen/qwen3-235b-a22b-thinking-2507": "Qwen/Qwen3-235B-A22B-Thinking-2507",
    "qwen/qwen3.5-9b": "Qwen/Qwen3.5-9B",
    "qwen/qwen3.5-27b": "Qwen/Qwen3.5-27B",
    "qwen/qwen3.5-122b-a10b": "Qwen/Qwen3.5-122B-A10B",
    "qwen/qwen3.5-397b-a17b": "Qwen/Qwen3.5-397B-A17B",
    "qwen/qwen3.6-27b": "Qwen/Qwen3.6-27B",
    "qwen/qwen3.8-27b": "Qwen/Qwen3.8-27B",
    # The free endpoint serves the same weights as the paid one.
    "qwen/qwen3.8-27b:free": "Qwen/Qwen3.8-27B",
}
