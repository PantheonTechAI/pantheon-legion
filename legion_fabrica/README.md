# Legion Fabrica Boundary

Fabrica owns the declared tool registry and execution broker. The first slice
provides an in-memory reference implementation with capability, side-effect,
filesystem, network, and credential policy metadata. It is not an MCP client
or sandbox implementation.

`AquilaService.invoke_read_tool` is the sole current control-plane entry point.
It obtains a fresh `READ_TOOL` decision, checks the Mission ROE capability
allow/deny lists, gives Fabrica a correlated authorization ID, and appends both
the decision and result to the Mission timeline. Only declared `READ` tools are
accepted; non-read tools must later be bound to an approved Mission Action and
the durable execution path.
