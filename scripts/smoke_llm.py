"""Synthetic live checks for the unified model; never sends project data."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def run():
    from PIL import Image as PILImage
    from autogen_core import Image
    from autogen_core.models import (
        AssistantMessage, FunctionExecutionResult, FunctionExecutionResultMessage,
        SystemMessage, UserMessage,
    )
    from llm import deepseek_flash, deepseek_model, deepseek_base_url

    results = {"model": deepseek_model, "endpoint": deepseek_base_url}
    # Bounded synthetic checks; ordinary application requests keep 12,000 tokens.
    bounds = {"max_tokens": 2048, "timeout": 90}
    try:
        response = await deepseek_flash.create(
            [UserMessage(content='Return JSON with exactly {"ok": true}.', source="user")],
            json_output=True, extra_create_args=bounds,
        )
        assert response.finish_reason == "stop" and json.loads(response.content) == {"ok": True}
        results["text_json"] = "passed"
        print(json.dumps(results), flush=True)

        image = Image(PILImage.new("RGB", (128, 128), color="red"))
        response = await deepseek_flash.create(
            [UserMessage(content=['Return JSON with the dominant color in English as "color".', image], source="user")],
            json_output=True, extra_create_args=bounds,
        )
        assert response.finish_reason == "stop" and json.loads(response.content)["color"].lower() == "red"
        results["vision"] = "passed"
        print(json.dumps(results), flush=True)

        tool = {"name": "get_probe_value", "description": "Get a synthetic test value.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}
        messages = [SystemMessage(content="Call get_probe_value once, then return its value as JSON with key value."),
                    UserMessage(content="Get the synthetic value using the tool.", source="user")]
        response = await deepseek_flash.create(
            messages, tools=[tool], extra_create_args={**bounds, "tool_choice": "required"},
        )
        assert isinstance(response.content, list) and len(response.content) == 1
        call = response.content[0]
        assert call.name == "get_probe_value" and json.loads(call.arguments) == {}
        messages += [AssistantMessage(content=response.content, thought=response.thought, source="assistant"),
                     FunctionExecutionResultMessage(content=[FunctionExecutionResult(
                         content='{"value": 314159}', name=call.name, call_id=call.id)])]
        response = await deepseek_flash.create(
            messages, tools=[tool], json_output=True,
            extra_create_args={**bounds, "tool_choice": "none"},
        )
        assert response.finish_reason == "stop" and json.loads(response.content)["value"] == 314159
        results["tool_round_trip"] = "passed"

        chunks = []
        async for chunk in deepseek_flash.create_stream(
            [UserMessage(content="Reply exactly STREAM_OK.", source="user")],
            tools=[tool], extra_create_args={**bounds, "tool_choice": "none"},
        ):
            if isinstance(chunk, str):
                chunks.append(chunk)
        assert "STREAM_OK" in "".join(chunks)
        results["streaming_with_tools"] = "passed"
        print(json.dumps(results), flush=True)
        return 0
    except Exception as exc:
        # Do not print SDK exceptions, which may contain request/response payloads.
        results["error"] = {"type": type(exc).__name__, "status": getattr(exc, "status_code", None)}
        print(json.dumps(results), flush=True)
        return 1
    finally:
        await deepseek_flash.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Make paid synthetic calls to the configured API.")
    args = parser.parse_args()
    if not args.live:
        parser.error("Pass --live to run external API checks.")
    sys.exit(asyncio.run(run()))
