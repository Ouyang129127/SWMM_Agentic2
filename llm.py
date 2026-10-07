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

deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")
deepseek_base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
# DeepSeek-V4.1-Flash is exposed by the official API as deepseek-flash.
# Legacy per-role model settings intentionally do not override this single model.
deepseek_model = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
request_timeout_seconds = float(os.environ.get("OPENAI_REQUEST_TIMEOUT_SECONDS", "300"))


def require_api_key(value, names):
    if value:
        return value
    joined_names = " or ".join(names)
    raise RuntimeError(
        f"Missing API key. Set {joined_names} in .env or in your shell before running main.py."
    )


class DeepSeekFlashClient(OpenAIChatCompletionClient):
    """Compatibility with the project's pinned AutoGen 0.6.1 client.

    AutoGen drops reasoning_content on tool-call responses and replay. Use
    non-thinking mode for requests with tools to avoid a subsequent HTTP 400;
    text, JSON diagnosis, coding and image requests keep high reasoning effort.
    This hook is shared by create() and create_stream().
    """

    def _process_create_args(self, *args, **kwargs):
        params = super()._process_create_args(*args, **kwargs)
        if params.tools:
            params.create_args["reasoning_effort"] = "none"
        return params


deepseek_flash = DeepSeekFlashClient(
    model=deepseek_model,
    base_url=deepseek_base_url,
    api_key=require_api_key(deepseek_api_key, ["DEEPSEEK_API_KEY"]),
    model_info={
        "vision": True,
        "function_calling": True,
        "json_output": True,
        "family": "unknown",
        "structured_output": False,
        "multiple_system_messages": True,
    },
    temperature=0,
    reasoning_effort="high",
    timeout=request_timeout_seconds,
)

# Compatibility aliases for external scripts; these all reference one client.
deepseekV3 = deepseekR1 = qwen = deepseek_flash
deepseek_chat_model = deepseek_reasoner_model = qwen_model = deepseek_model
