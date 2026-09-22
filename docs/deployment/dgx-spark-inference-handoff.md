# DGX Spark inference deployment handoff

- Status: Observed development deployment; not production-ready
- Observations recorded: 2026-09-21
- Documentation updated: 2026-09-22
- Scope: DGX Spark host/runtime operations and measured evidence
- Related architecture: [Authorized Spark Cognition Loop plan](../architecture/spark-inference-cognition-plan.md), [ADR-007](../adr/ADR-007-capability-selected-authorized-cognition.md)

## Purpose and authority

This document preserves the observed DGX Spark deployment state and the manual
inference experiments that informed Legion's next implementation slice. These
are dated deployment facts, not permanent architectural requirements.

The Spark remains primarily a model-serving compute node. It does not own
Mission state, Aquila authorization, Tabula credentials, Legion tool execution,
or other organizational authority. A healthy model endpoint and possession of
a tool schema grant no permission to execute that tool.

Legion's current deployment scripts do not install, configure, restart, or
upgrade the Spark host, vLLM container, model, firewall, or dashboard. Any such
operational change must be performed separately and this evidence revalidated.

## Network and management

| Item | Observed value |
|---|---|
| Hostname | `spark` |
| FQDN | `spark.texasfight.net` |
| SSH management | TCP/22 |
| DGX Dashboard on Spark | `localhost:11000` |
| Inference service | TCP/8000 |
| OpenAI-compatible API root | `http://spark:8000/v1` |

Access the dashboard through an SSH tunnel; do not expose it through the
firewall:

```sh
ssh -L 11000:localhost:11000 jtdauria@spark
```

Then open `http://localhost:11000` locally.

OPNsense currently permits the required cross-subnet path from the Olares One
host (`ai`) to Spark TCP/8000. From Olares One, this was confirmed:

```sh
curl http://spark:8000/v1/models
```

The successful path is reachability evidence, not an authentication or
authorization control.

## Observed hardware and platform

| Item | Observed value |
|---|---|
| Platform | NVIDIA DGX Spark |
| SoC | GB10 Grace Blackwell |
| Unified memory | approximately 128 GB; 121 GiB visible to Linux |
| Host CUDA | 13.0 |
| Docker | 29.6.2 |
| NVIDIA Container Toolkit | 1.20.1 |
| Root NVMe | approximately 1.8 TB |
| Initially available storage | approximately 1.7 TB |

GPU containers were validated successfully. These values describe the current
host; Legion architecture must not require this accelerator, memory size, CUDA
version, or container stack.

## Known-good primary inference service

| Item | Observed/configured value |
|---|---|
| Runtime | vLLM 0.29.0 |
| Image | `vllm/vllm-openai:latest` |
| Container | `vllm-server` |
| Restart policy | `unless-stopped` |
| Model | `nvidia/Qwen3.6-35B-A3B-NVFP4` |
| Context limit | 131,072 tokens |
| Endpoint | `http://spark:8000/v1` |

The known-good deployment includes all three options:

```text
--reasoning-parser qwen3
--tool-call-parser qwen3_xml
--enable-auto-tool-choice
```

Do not omit or casually change these options. Without the reasoning parser,
Qwen placed chain/reasoning text in `message.content` and frequently exhausted
`max_tokens` before producing a final answer. With it enabled, vLLM separated
approximately 138 reasoning tokens into `message.reasoning` and returned the
expected concise final content with `finish_reason=stop` in the observed probe.

`/v1/models` and `/health` were reachable from the Legion host on 2026-09-21.
Model identity, context, reasoning separation, and tool calling must be
revalidated after changing the image, runtime, model, parser profile, or launch
configuration. A model-list response alone does not prove parser behavior.

## Validated OpenAI-compatible tool behavior

The model was given a logical tool schema:

```text
tabula_search(query: string)
```

For a request to find Aquila architecture documentation, Qwen returned one
typed tool call with arguments equivalent to:

```json
{"query":"Aquila architecture documentation"}
```

The response had `content=null`, a separate reasoning field, and
`finish_reason=tool_calls`. This demonstrated that the model could identify a
need for evidence, select the advertised logical capability, produce typed
arguments, and stop for execution.

A simulated Tabula result was then returned through the standard sequence:

```text
user
  -> assistant(tool_calls)
  -> tool(tool_call_id, result)
  -> assistant
```

Qwen did not call the tool again, used the supplied Aquila evidence, produced a
concise final answer, and returned `finish_reason=stop`. The final continuation
reported zero additional reasoning tokens in this observation.

This validates Spark/vLLM/Qwen protocol behavior only. It does not authorize a
tool or prove the Legion-side authority, persistence, or recovery path. That
remaining work is specified by the Authorized Spark Cognition Loop plan.

## Measured performance baseline

The observed single-request vLLM benchmark was:

| Measurement | Value |
|---|---|
| Prompt tokens | 40 |
| Completion tokens | 1,024 |
| Total tokens | 1,064 |
| Wall time | 12.67 seconds |
| Approximate decode throughput | 80.8 output tokens/second |

This is a dated measured offering observation, not a vendor estimate, node-wide
capacity, concurrency result, service-level objective, or routing guarantee.
Future measurements should retain model/runtime/configuration identity and
measurement time.

## NVFP4 and Marlin finding

vLLM selected:

```text
MarlinNvFp4LinearKernel
MARLIN NvFp4 MoE backend
```

Although GB10 supports Blackwell FP4, current NVIDIA/vLLM Spark recipes also
use Marlin for this workload. Marlin selection must not currently be treated as
a broken or unsupported configuration without new contrary evidence.

## TensorRT-LLM experiment

| Item | Observed value |
|---|---|
| Image | `nvcr.io/nvidia/tensorrt-llm/release:1.3.0rc13` |
| TensorRT-LLM version | 1.3.0rc13 |
| Model | `nvidia/Qwen3-30B-A3B-FP4` |
| Test endpoint | `http://spark:8355` |
| 1,024-token wall time | 61.98 seconds |
| Approximate throughput | 16.5 output tokens/second |

The runtime successfully used native SM120/NVFP4 paths including
`trtllm::nvfp4_gemm::gemm`, `cutlass::arch::Sm120`, and `__nv_fp4_e2m1`.

The TensorRT-LLM and vLLM models were not identical, so this is not a controlled
runtime benchmark. The practical result nevertheless favors vLLM as the current
general-purpose Legion provider. TensorRT-LLM remains a possible model-specific
path only when a controlled benchmark justifies it.

## Failed optimization experiment

An aggressive vLLM configuration combined:

- 262,144-token context;
- FP8 KV cache;
- FlashInfer;
- Marlin MoE;
- MTP speculative decoding;
- fastsafetensors;
- asynchronous scheduling;
- prefix caching; and
- the reasoning and tool parsers.

Initialization failed with:

```text
moe_backend='marlin' is not supported for unquantized MoE
```

The main NVFP4 model supported Marlin. The conflict occurred while initializing
Qwen's MTP speculative model: its MoE path was unquantized and conflicted with
the global Marlin backend.

Do not re-enable this optimization bundle wholesale. Start from the known-good
configuration, change one independently measurable setting at a time, retain
the exact model/runtime configuration, and re-run reasoning/tool conformance as
well as performance checks.

## Architecture mapping

The current deployment maps to the reviewed contracts as follows:

| Contract identity | Initial deployment value |
|---|---|
| `ComputeNode` | `spark` |
| `InferenceEndpoint` | Spark TCP/8000 origin |
| `InferenceProvider` | OpenAI-compatible adapter over vLLM 0.29.0 |
| `ModelOffering` | `nvidia/Qwen3.6-35B-A3B-NVFP4` |

Spark is not “the LLM.” It is one node that may later expose several endpoints
and provider services. The Qwen model is one offering on the current vLLM
provider. The same model may be offered elsewhere, and Spark may host NIM,
TensorRT-LLM, or other models without changing Agent or WorkItem identity.

The current runtime decision is:

- vLLM: primary general-purpose local cognition provider;
- TensorRT-LLM: optional model-specific path when controlled evidence supports
  it; and
- NIM: optional packaged NVIDIA service when appropriate.

## Security readiness gate

TCP/8000 is currently protected primarily by network/firewall policy. vLLM API
authentication has not been configured. The direct cleartext endpoint is not a
production-ready Legion provider.

Before production enablement:

1. place authenticated, route-restricting ingress, mTLS, or an equivalent
   boundary in front of vLLM;
2. restrict sources and exposed routes; keep OPNsense policy as defense in depth;
3. store only an opaque credential reference in provider configuration and
   resolve the secret at the Cognition transport boundary;
4. never commit model API keys or put them in model context, Mission state,
   Runtime persistence, audit, or Resource Fabric;
5. keep the dashboard on loopback and use the SSH tunnel; and
6. confirm Spark cannot obtain Aquila, Tabula, STS, database, shell, or tool
   credentials and cannot grant itself additional authority.

The opt-in live acceptance runner may use the current endpoint only with the
plan's two explicit insecure-development acknowledgements. Production
composition must fail closed without the controls above.

## Observability follow-up

vLLM exposes `/health` and `/metrics`. Future Legion/homelab collection should
include:

- health and model availability;
- request count and error rate;
- time to first token and decode throughput;
- active requests and queue depth;
- context/KV utilization; and
- model, provider-runtime, endpoint, and node identities.

Measurements must be attached to the correct contract identity: generic
compute/memory capacity to the node, service health/queue to the endpoint, and
model/context/TTFT/decode results to the offering. Collection and alerting are
not implemented by the current planning slice.

## Legion integration evidence — 2026-09-22

The implemented Legion-side loop has now passed the actual isolated live
acceptance test twice, including after review remediation:

```text
Mission
  -> persistent Scout / CognitionRequirement
  -> ModelOffering -> InferenceProvider -> InferenceEndpoint -> ComputeNode
  -> Spark/Qwen tabula_search request
  -> Runtime validation
  -> fresh Aquila knowledge authority
  -> bounded Tabula retrieval
  -> tool result returned to Qwen
  -> grounded final WorkResult
  -> safe Runtime/Aquila/Tabula correlations and Mission inspection
```

The owner accepted ADR-007 and authorized the separate Tabula bounded-content
correction. Both runs used real Spark inference plus a fresh disposable Tabula
Corpus, a random review code present only in retrieved evidence, and an
out-of-scope control. See [the live evidence and review](../architecture/tabula-bounded-evidence-review.md).
On the final run the persisted tool turn took 2158 ms (394 prompt / 161
completion tokens, including 129 reasoning tokens); the final turn took 8003 ms
(391 prompt / 621 completion tokens, including 558 reasoning tokens). These are
individual offering observations, not capacity/throughput guarantees. Explicit
reasoning text was discarded; only safe usage counts were persisted.

`/version` returned `0.29.0`; `/v1/models` advertised the same Qwen model and
131072-token context. No Spark runtime, parser, firewall, or credential setting
was changed. Final delivery review is tracked separately; the production
security gates above remain closed.
