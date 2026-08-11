import os
from pathlib import Path
from autogen_ext.models.openai import OpenAIChatCompletionClient


def load_dotenv(path=".env"):
    env_path = Path(path)
    if not env_path.is_absolute():
        env_path = Path(__file__).resolve().parent / env_path

    if not env_path.exists():
        return

    with open(env_path, "r", encoding="utf-8-sig") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()

deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
qwen_api_key = os.environ.get("QWEN_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")

deepseek_base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.siliconflow.cn/v1")
deepseek_chat_model = os.environ.get("DEEPSEEK_CHAT_MODEL", "deepseek-ai/DeepSeek-V3.2")
deepseek_reasoner_model = os.environ.get("DEEPSEEK_REASONER_MODEL", "deepseek-ai/DeepSeek-V3.1-Terminus")
qwen_base_url = os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
qwen_model = os.environ.get("QWEN_MODEL", "qwen-vl-max")
request_timeout_seconds = float(os.environ.get("OPENAI_REQUEST_TIMEOUT_SECONDS", "120"))


def require_api_key(value, names):
    if value:
        return value
    joined_names = " or ".join(names)
    raise RuntimeError(
        f"Missing API key. Set {joined_names} in .env or in your shell before running main.py."
    )


deepseekV3 = OpenAIChatCompletionClient(
    model=deepseek_chat_model,
    base_url=deepseek_base_url,
    api_key=require_api_key(deepseek_api_key, ["DEEPSEEK_API_KEY", "OPENAI_API_KEY"]),
    model_info={
        "vision": True,
        "function_calling": True,
        "json_output": True,
        "family": "unknown",
        "structured_output": False,
        "multiple_system_messages": True,
    },
    seed=42,
    temperature=0,
    timeout=request_timeout_seconds,
)


deepseekR1 = OpenAIChatCompletionClient(
    model=deepseek_reasoner_model,
    base_url=deepseek_base_url,
    api_key=require_api_key(deepseek_api_key, ["DEEPSEEK_API_KEY", "OPENAI_API_KEY"]),
    model_info={
        "vision": True,
        "function_calling": True,
        "json_output": True,
        "family": "unknown",
        "structured_output": False,
        "multiple_system_messages": True,
    },
    seed=42,
    temperature=0,
    max_tokens=12000,
    timeout=request_timeout_seconds,
)


qwen = None
if qwen_api_key:
    qwen = OpenAIChatCompletionClient(
        model=qwen_model,
        base_url=qwen_base_url,
        api_key=qwen_api_key,
        model_info={
            "vision": True,
            "function_calling": True,
            "json_output": True,
            "family": "unknown",
            "structured_output": False,
            "multiple_system_messages": True,
        },
        seed=42,
        temperature=0,
        max_tokens=6000,
        timeout=request_timeout_seconds,
    )
