"""Strands public Model adapter. Only the host bridge can perform inference."""

import json

from strands.models.model import Model

from .protocol import ProxyRefused


def provider_messages(messages, system_prompt=None, system_prompt_content=None):
    converted = []
    if system_prompt_content is not None:
        if any(set(block) != {"text"} for block in system_prompt_content):
            raise ProxyRefused("UNSUPPORTED_SYSTEM_CONTENT")
        system_prompt = "\n".join(block["text"] for block in system_prompt_content)
    if system_prompt:
        converted.append({"role": "system", "content": system_prompt})
    for message in messages:
        if set(message) != {"role", "content"} or message["role"] not in {"user", "assistant"}:
            raise ProxyRefused("UNSUPPORTED_MESSAGE")
        text, calls, results = [], [], []
        for block in message["content"]:
            if set(block) == {"text"} and isinstance(block["text"], str):
                text.append(block["text"])
            elif set(block) == {"toolUse"} and message["role"] == "assistant":
                use = block["toolUse"]
                if set(use) != {"toolUseId", "name", "input"}:
                    raise ProxyRefused("UNSUPPORTED_TOOL_REQUEST")
                calls.append({"id": use["toolUseId"], "type": "function", "function": {
                    "name": use["name"], "arguments": json.dumps(use["input"], allow_nan=False)}})
            elif set(block) == {"toolResult"} and message["role"] == "user":
                result = block["toolResult"]
                if set(result) - {"toolUseId", "content", "status"}:
                    raise ProxyRefused("UNSUPPORTED_TOOL_RESULT")
                for item in result["content"]:
                    if set(item) not in ({"text"}, {"json"}):
                        raise ProxyRefused("UNSUPPORTED_TOOL_RESULT")
                results.append({"role": "tool", "tool_call_id": result["toolUseId"],
                                "content": json.dumps(result["content"], allow_nan=False)})
            else:
                # Explicit reasoning, images, executable blocks and hidden extra
                # message fields are not part of this text-only spike profile.
                raise ProxyRefused("UNSUPPORTED_CONTENT")
        if text or calls:
            converted.append({"role": message["role"], "content": "\n".join(text) or None,
                              **({"tool_calls": calls} if calls else {})})
        converted.extend(results)
    if len(json.dumps(converted, ensure_ascii=False).encode("utf-8")) > 64 * 1024:
        raise ProxyRefused("MESSAGE_BOUND_EXCEEDED")
    return converted


class LegionProxyModel(Model):
    def __init__(self, client):
        self.client = client

    def get_config(self):
        # Observability label only. Provider/model/endpoint selection stays host-side.
        return {"model_id": "legion-authorized-proxy"}

    def update_config(self, **config):
        if config:
            raise ProxyRefused("TRUSTED_CONFIGURATION_ONLY")

    async def structured_output(self, *args, **kwargs):
        raise ProxyRefused("STRUCTURED_OUTPUT_NOT_ENABLED")
        yield

    async def stream(self, messages, tool_specs=None, system_prompt=None, *,
                     system_prompt_content=None, cancel_signal=None, **kwargs):
        if cancel_signal is not None and cancel_signal.is_set():
            raise ProxyRefused("CANCELLED_BEFORE_PROXY")
        response = self.client.call("model", messages=provider_messages(
            messages, system_prompt, system_prompt_content), tool_names=[tool["name"] for tool in tool_specs or []])
        yield {"messageStart": {"role": "assistant"}}
        blocks = []
        if response["content"]:
            blocks.append({"text": response["content"]})
        blocks.extend({"toolUse": call} for call in response["tool_calls"])
        for index, block in enumerate(blocks):
            if "text" in block:
                yield {"contentBlockStart": {"start": {}, "contentBlockIndex": index}}
                yield {"contentBlockDelta": {"delta": block, "contentBlockIndex": index}}
            else:
                use = block["toolUse"]
                yield {"contentBlockStart": {"start": {"toolUse": {
                    "toolUseId": use["toolUseId"], "name": use["name"]}}, "contentBlockIndex": index}}
                yield {"contentBlockDelta": {"delta": {"toolUse": {
                    "input": json.dumps(use["input"], allow_nan=False)}}, "contentBlockIndex": index}}
            yield {"contentBlockStop": {"contentBlockIndex": index}}
        yield {"messageStop": {"stopReason": "tool_use" if response["tool_calls"] else "end_turn"}}
        yield {"metadata": {"usage": response["usage"], "metrics": {"latencyMs": 0}}}
