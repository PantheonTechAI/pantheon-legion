"""Worker-local, content-safe OTel experiment; no external exporter."""

from opentelemetry import context, trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


SENTINELS = ("SECRET_SENTINEL_DO_NOT_RETAIN", "EXPLICIT_REASONING_SENTINEL_DO_NOT_RETAIN",
             "PROMPT_SENTINEL_DO_NOT_RETAIN", "EVIDENCE_SENTINEL_DO_NOT_RETAIN",
             "TOOL_ARG_SENTINEL_DO_NOT_RETAIN", "TOOL_RESULT_SENTINEL_DO_NOT_RETAIN")
TOKEN_KEYS = frozenset({"gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens",
                        "gen_ai.usage.prompt_tokens", "gen_ai.usage.completion_tokens"})


class TraceCapture:
    def __init__(self, trace_id, parent_id):
        self.exporter = InMemorySpanExporter()
        self.provider = TracerProvider()
        self.provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        trace.set_tracer_provider(self.provider)
        parent = trace.NonRecordingSpan(trace.SpanContext(
            trace_id=int(trace_id, 16), span_id=int(parent_id, 16), is_remote=True,
            trace_flags=trace.TraceFlags(trace.TraceFlags.SAMPLED)))
        self.token = context.attach(trace.set_span_in_context(parent))

    def finish(self):
        self.provider.force_flush()
        spans = self.exporter.get_finished_spans()
        # Inspect native spans/events/exceptions BEFORE the export allowlist. A
        # sentinel failure makes the host refuse success, never merely drop it.
        leak = any(sentinel in span.to_json() for span in spans for sentinel in SENTINELS)
        bounded = len(spans) <= 128
        records = [{"trace_id": format(span.context.trace_id, "032x"),
                    "span_id": format(span.context.span_id, "016x"),
                    "parent_id": format(span.parent.span_id, "016x") if span.parent else "0" * 16,
                    "duration_ns": max(0, span.end_time - span.start_time),
                    "error": span.status.is_ok is False,
                    "tokens": {key: value for key, value in span.attributes.items()
                               if key in TOKEN_KEYS and type(value) is int and value >= 0}}
                   for span in spans[:128]]
        context.detach(self.token)
        self.provider.shutdown()
        return {"leak_detected": leak or not bounded, "spans": records}
