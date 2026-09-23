"""Replaceable read-only observer for a direct local Docker/vLLM deployment."""

from datetime import datetime, timezone
import ipaddress
import json
import os
import re
import selectors
import shlex
import socket
import subprocess
import time
from urllib.parse import urlsplit

from .capability import CognitionError
from .openai_compatible import strict_json


# Run on the management host; only allowlisted metadata leaves that host.
# Docker environment/full argument lists may contain credentials and are never printed.
COLLECTOR = r'''
import json, subprocess, sys
try:
    shape = '{"Id":{{json .Id}},"Image":{{json .Image}},"Path":{{json .Path}},"Args":{{json .Args}},' + \
            '"State":{"Running":{{json .State.Running}},"StartedAt":{{json .State.StartedAt}}},' + \
            '"HostConfig":{"NetworkMode":{{json .HostConfig.NetworkMode}}},' + \
            '"NetworkSettings":{"Ports":{{json .NetworkSettings.Ports}}}}'
    p = subprocess.run(["docker", "inspect", "--type=container", "--format", shape, sys.argv[1]],
                       capture_output=True, timeout=8, check=True)
    if len(p.stdout) > 1048576: raise ValueError()
    c = json.loads(p.stdout)
    args = c["Args"]
    def option(name, default=None):
        values = []
        for i, arg in enumerate(args):
            if arg == name: values.append(args[i+1])
            elif arg.startswith(name + "="): values.append(arg[len(name)+1:])
        if len(values) > 1: raise ValueError()
        return values[0] if values else default
    if any(a == "--config" or a.startswith("--config=") for a in args): raise ValueError()
    model = option("--model")
    if model is None and "serve" in args: model = args[args.index("serve") + 1]
    path = c["Path"]
    if not (path.rsplit("/", 1)[-1] in ("vllm", "python", "python3", "python3.12")
            and ("serve" in args or "vllm.entrypoints.openai.api_server" in args)):
        raise ValueError()
    auto = [a for a in args if a == "--enable-auto-tool-choice" or a.startswith("--enable-auto-tool-choice=")]
    value = {"container_id": c["Id"], "image_id": c["Image"], "started_at": c["State"]["StartedAt"],
        "running": c["State"]["Running"], "model_id": model,
        "max_model_len": int(option("--max-model-len", "0")),
        "reasoning_parser": option("--reasoning-parser"), "tool_call_parser": option("--tool-call-parser"),
        "auto_tool_choice": auto == ["--enable-auto-tool-choice"],
        "listen_port": int(option("--port", "8000")), "listen_host": option("--host", "0.0.0.0"),
        "network_mode": c["HostConfig"]["NetworkMode"], "ports": c["NetworkSettings"]["Ports"]}
    encoded = json.dumps(value)
    if len(encoded) > 8192: raise ValueError()
    print(encoded)
except Exception:
    sys.exit(1)
'''


def bounded_process(argv, *, timeout=15, limit=16384):
    """Bound output while reading, not after an unbounded communicate buffer."""
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    output = bytearray()
    deadline = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise CognitionError("VALIDATION_OBSERVATION_UNAVAILABLE")
                part = os.read(process.stdout.fileno(), min(4096, limit + 1 - len(output)))
                if not part:
                    break
                output.extend(part)
                if len(output) > limit:
                    raise CognitionError("VALIDATION_OBSERVATION_INVALID")
        if process.wait(timeout=max(0.01, deadline - time.monotonic())) != 0:
            raise CognitionError("VALIDATION_OBSERVATION_UNAVAILABLE")
        return bytes(output)
    except (OSError, subprocess.TimeoutExpired):
        raise CognitionError("VALIDATION_OBSERVATION_UNAVAILABLE") from None
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


class VllmSshObserver:
    def __init__(self, *, host, user, container, execute=bounded_process):
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}", host)
                or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,63}", user)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", container)):
            raise CognitionError("VALIDATION_OBSERVER_CONFIG_INVALID")
        self.host, self.user, self.container, self.execute = host, user, container, execute

    def observe(self, candidate):
        try:
            endpoint = urlsplit(candidate.endpoint.origin)
            # Initial direct-host profile has no proxy/bastion-to-endpoint topology.
            host_ips = {item[4][0] for item in socket.getaddrinfo(self.host, None, type=socket.SOCK_STREAM)}
            endpoint_ips = {item[4][0] for item in socket.getaddrinfo(endpoint.hostname, None, type=socket.SOCK_STREAM)}
            if not host_ips or host_ips != endpoint_ips:
                raise CognitionError("VALIDATION_MANAGEMENT_ENDPOINT_MISMATCH")
            command = "python3 -c " + shlex.quote(COLLECTOR) + " " + shlex.quote(self.container)
            raw = self.execute(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                "-o", "ConnectTimeout=5", "-o", "ClearAllForwardings=yes",
                "-o", "PermitLocalCommand=no", "-o", "RemoteCommand=none",
                "-o", "Hostname=" + self.host, "-o", "ProxyCommand=none", "-o", "ProxyJump=none",
                self.user + "@" + self.host, command])
            value = strict_json(raw)
            expected_keys = {"container_id", "image_id", "started_at", "running", "model_id", "max_model_len",
                "reasoning_parser", "tool_call_parser", "auto_tool_choice", "listen_port", "listen_host", "network_mode", "ports"}
            if not isinstance(value, dict) or set(value) != expected_keys:
                raise ValueError
            if (not re.fullmatch(r"[a-f0-9]{64}", value["container_id"])
                    or not re.fullmatch(r"sha256:[a-f0-9]{64}", value["image_id"])):
                raise ValueError
            datetime.fromisoformat(value["started_at"].replace("Z", "+00:00"))
            if (value["running"] is not True or value["model_id"] != candidate.offering.model_id
                    or type(value["max_model_len"]) is not int or value["max_model_len"] != candidate.offering.context_window
                    or value["reasoning_parser"] != "qwen3" or value["tool_call_parser"] != "qwen3_xml"
                    or value["auto_tool_choice"] is not True):
                raise CognitionError("VALIDATION_DEPLOYMENT_MISMATCH")
            port = endpoint.port or (443 if endpoint.scheme == "https" else 80)
            if type(value["listen_port"]) is not int or not 1 <= value["listen_port"] <= 65535:
                raise ValueError
            if value["listen_host"] not in {"0.0.0.0", "::"}:
                raise CognitionError("VALIDATION_PORT_MISMATCH")
            if value["network_mode"] == "host":
                if value["listen_port"] != port:
                    raise CognitionError("VALIDATION_PORT_MISMATCH")
            else:
                bindings = value["ports"].get(str(value["listen_port"]) + "/tcp") or []
                if not any(item["HostPort"] == str(port) and
                           (item["HostIp"] in {"0.0.0.0", "::"} or item["HostIp"] in endpoint_ips)
                           for item in bindings):
                    raise CognitionError("VALIDATION_PORT_MISMATCH")
            # Do not persist arbitrary maps/host aliases or other Docker arguments.
            identity = {key: value[key] for key in ("container_id", "image_id", "started_at", "model_id",
                "max_model_len", "reasoning_parser", "tool_call_parser", "auto_tool_choice", "listen_port")}
            identity.update(endpoint_origin=candidate.endpoint.origin, endpoint_port=port,
                            address_set=sorted(str(ipaddress.ip_address(ip)) for ip in endpoint_ips))
            return {"observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "identity": identity}
        except CognitionError:
            raise
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            raise CognitionError("VALIDATION_OBSERVATION_INVALID") from None
