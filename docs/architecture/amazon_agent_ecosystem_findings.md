# Amazon agent ecosystem — sourced planning findings

- Date checked: 2026-09-22
- Status: Research supporting the owner-supplied revised Strands spike;
  recommendations are not accepted production architecture changes.
- Requirements: [normalized owner baseline](strands_legion_spike_requirements.md)

## Findings and provenance

| Project | Primary source | Planning disposition |
|---|---|---|
| Strands Python SDK | [Published 1.56.0 package](https://pypi.org/project/strands-agents/1.56.0/), [source repository](https://github.com/strands-agents/harness-sdk) | Prototype; adopt only if evidence justifies the adapters and dependency cost |
| Pizza Bot | [Repository](https://github.com/pizza-bot-app/pizza-bot), [Amazon introduction](https://aws.amazon.com/blogs/opensource/introducing-pizza-bot-an-open-source-inbox-for-ai-agents-that-work-in-the-background/) | Borrow asynchronous queues and durable decisions; its DeepAgents/LangGraph implementation does not validate Strands |
| Dogwood | [Reference interpreter](https://github.com/dogwood-policy/dogwood), [Amazon introduction](https://aws.amazon.com/blogs/opensource/introducing-dogwood-runtime-verification-for-ai-agents/) | Study temporal policies separately; maintainers explicitly warn against using the reference interpreter as production enforcement |
| Agent Plugins | [Specification 1.0.0](https://github.com/agentplugins/agent-plugins-spec/blob/main/spec/1.0.0.md), [AWS support announcement](https://aws.amazon.com/blogs/opensource/aws-supports-agent-plugins-an-open-standard-for-portable-agent-extensions/) | Portable skills/MCP packaging reference, not permission or automatic execution |
| Loom | [AWS Labs repository](https://github.com/awslabs/loom), [Amazon introduction](https://aws.amazon.com/blogs/opensource/building-secure-ai-agents-at-scale-introducing-loom-for-aws/) | Learn lifecycle and identity patterns; not Legion's control plane |
| AgentCore | [AWS developer guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) | Managed runtime reference, not a local-first dependency |
| Open Agentic Platform | [AWS Labs repository](https://github.com/awslabs/open-agentic-platform) | Declarative infrastructure reference; EKS deployment work is outside this spike |

Except the pinned Python package and versioned plugin specification, these are
dated research observations, not tested release certifications. Capture exact
source commits before any later integration of the research-only projects.

## What must be tested, not assumed

The [OpenAI-compatible model adapter](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/models/openai.py)
currently offers client injection, a possible seam for governed network policy.
The implementation spike must inspect the **1.56.0 distribution**, not infer
its API from moving `main`. Prefer a Legion-owned Strands `Model` adapter
which delegates actual IO to existing Cognition Fabric. Stock provider
experiments do not count as authorized Legion integration.

The [session API reference](https://strandsagents.com/docs/api/python/strands.session.snapshot_session_manager/)
and [moving source](https://github.com/strands-agents/harness-sdk/blob/main/strands-py/src/strands/session/snapshot_session_manager.py)
have exposed different Graph/Swarm support descriptions. Session restoration,
save timing and orchestrator support must therefore be recorded per installed
version. No claim of multi-agent crash recovery follows from single-agent
session persistence.

The [tracing reference](https://strandsagents.com/docs/api/python/strands.telemetry.tracer/)
documents sensitive message/tool attributes and redaction controls. Native
telemetry is a privacy experiment until actual collected events, logs and
exception paths pass sentinel tests. Default SDK logging/export configuration
is not Legion policy.

## Architecture conclusion

External projects support evaluating reusable infrastructure; they do not
change Legion's ownership. Aquila authorizes; Runtime owns the persistent
organization and work; Cognition/Resource Fabric select and provide cognition;
Tabula supplies separately authorized evidence; Fabrica enforces effects.
Framework objects, installed capabilities, session state and handoffs cannot
create any of those authorities.
