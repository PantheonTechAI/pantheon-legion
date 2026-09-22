"""Bounded synchronous transport. Provider secrets and raw reasoning stop here."""

from dataclasses import dataclass
import json
import socket
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import warnings

from .capability import CognitionError, CognitionTurnResult, RequestedToolCall


def strict_json(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY")
            result[key] = item
        return result

    def invalid_constant(value):
        raise ValueError("INVALID_JSON_CONSTANT")

    return json.loads(value, object_pairs_hook=pairs, parse_constant=invalid_constant)


@dataclass(frozen=True)
class TransportPolicy:
    mode: str = "production"
    authenticated_restricted_ingress: bool = False
    acknowledge_cleartext: bool = False
    acknowledge_unauthenticated: bool = False
    timeout_seconds: float = 30.0
    max_request_bytes: int = 128 * 1024
    max_response_bytes: int = 128 * 1024

    def __post_init__(self):
        if self.mode not in {"production", "live_acceptance"}:
            raise ValueError("INVALID_TRANSPORT_MODE")
        for flag in (self.authenticated_restricted_ingress, self.acknowledge_cleartext,
                     self.acknowledge_unauthenticated):
            if type(flag) is not bool:
                raise ValueError("INVALID_TRANSPORT_FLAG")
        if type(self.timeout_seconds) not in {int, float} or not 0 < self.timeout_seconds <= 120:
            raise ValueError("INVALID_TRANSPORT_TIMEOUT")
        for limit in (self.max_request_bytes, self.max_response_bytes):
            if type(limit) is not int or not 1024 <= limit <= 128 * 1024:
                raise ValueError("INVALID_TRANSPORT_BOUND")


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class OpenAICompatibleTransport:
    def __init__(self, *, policy: TransportPolicy = TransportPolicy(),
                 secret_supplier: Callable[[str], str] | None = None):
        self.policy = policy
        self.secret_supplier = secret_supplier
        self._opener = build_opener(ProxyHandler({}), _NoRedirects())
        if policy.mode == "live_acceptance":
            if not (policy.acknowledge_cleartext and policy.acknowledge_unauthenticated):
                raise CognitionError("INSECURE_ACCEPTANCE_ACKNOWLEDGEMENTS_REQUIRED")
            warnings.warn("Explicit development inference transport enabled; not production-ready.",
                          RuntimeWarning, stacklevel=2)

    def validate_configuration(self, endpoint, provider):
        if self.policy.mode == "production" and (
                not endpoint.origin.startswith("https://")
                or not provider.credential_reference
                or not self.policy.authenticated_restricted_ingress):
            raise CognitionError("COGNITION_PRODUCTION_SECURITY_REQUIRED")

    def _request(self, endpoint, provider, route, payload=None):
        self.validate_configuration(endpoint, provider)
        headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
        if provider.credential_reference is not None:
            try:
                secret = self.secret_supplier(provider.credential_reference) if self.secret_supplier else None
                if not isinstance(secret, str) or not secret or len(secret) > 4096 or any(
                        ord(c) <= 32 or ord(c) >= 127 for c in secret):
                    raise ValueError
                headers["Authorization"] = "Bearer " + secret
            except Exception:
                raise CognitionError("COGNITION_CREDENTIAL_UNAVAILABLE") from None
        data = None
        if payload is not None:
            try:
                data = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                                  separators=(",", ":")).encode("utf-8")
            except (ValueError, TypeError, UnicodeError):
                raise CognitionError("COGNITION_REQUEST_INVALID") from None
            if len(data) > self.policy.max_request_bytes:
                raise CognitionError("COGNITION_REQUEST_TOO_LARGE")
            headers["Content-Type"] = "application/json"
        try:
            request = Request(endpoint.origin.rstrip("/") + route, data=data, headers=headers)
            with self._opener.open(request, timeout=self.policy.timeout_seconds) as response:
                if response.status != 200:
                    raise CognitionError("COGNITION_HTTP_ERROR")
                body = response.read(self.policy.max_response_bytes + 1)
                if len(body) > self.policy.max_response_bytes:
                    raise CognitionError("COGNITION_RESPONSE_TOO_LARGE")
                return body
        except HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            exc.close()
            raise CognitionError("COGNITION_HTTP_ERROR", retryable=retryable) from None
        except (URLError, TimeoutError, socket.timeout, ConnectionError, OSError):
            raise CognitionError("COGNITION_TRANSPORT_UNAVAILABLE", retryable=True) from None
        except CognitionError:
            raise
        except Exception:
            raise CognitionError("COGNITION_TRANSPORT_INVALID") from None

    def available(self, endpoint, provider, offering):
        try:
            self._request(endpoint, provider, "/health")
            response = strict_json(self._request(endpoint, provider, provider.api_prefix + "/models"))
            models = response["data"]
            if not isinstance(models, list) or len(models) > 256:
                return False
            matches = [model for model in models if isinstance(model, dict) and model.get("id") == offering.model_id]
            if len(matches) != 1:
                return False
            context = matches[0].get("max_model_len")
            # Missing advertised context cannot validate the configured hard bound.
            return type(context) is int and context >= offering.context_window
        except (CognitionError, ValueError, TypeError, KeyError, UnicodeError):
            return False

    def chat(self, endpoint, provider, offering, messages, *, tools=()):
        payload = {
            "model": offering.model_id, "messages": messages,
            "max_tokens": 2048, "temperature": 0, "stream": False,
            "parallel_tool_calls": False,
        }
        if tools:
            payload["tools"] = list(tools)
            payload["tool_choice"] = "auto"
        return self.parse(self._request(endpoint, provider, provider.api_prefix + "/chat/completions", payload))

    @staticmethod
    def parse(body):
        try:
            if not isinstance(body, bytes) or len(body) > 128 * 1024:
                raise ValueError
            value = strict_json(body)
            choices = value["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError
            choice = choices[0]
            message = choice["message"]
            if message.get("role") != "assistant" or choice.get("index", 0) != 0:
                raise ValueError
            if message.get("reasoning") is not None and not isinstance(message["reasoning"], str):
                raise ValueError
            # Explicit reasoning is intentionally absent from every returned value.
            calls = message.get("tool_calls")
            if calls is None:
                calls = []
            if not isinstance(calls, list) or len(calls) > 8:
                raise ValueError
            parsed_calls = []
            for call in calls:
                if call["type"] != "function" or not isinstance(call["function"], dict):
                    raise ValueError
                parsed_calls.append(RequestedToolCall(call["id"], call["function"]["name"],
                                                       call["function"]["arguments"]))
            usage = value.get("usage") or {}
            details = usage.get("completion_tokens_details") or {}
            return CognitionTurnResult(
                response_id=value["id"], finish_reason=choice["finish_reason"],
                content=message.get("content"), tool_calls=tuple(parsed_calls),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                reasoning_tokens=details.get("reasoning_tokens", 0),
            )
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
            raise CognitionError("COGNITION_RESPONSE_INVALID") from None
