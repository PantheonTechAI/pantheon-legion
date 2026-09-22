# Static inference resources

Resource Fabric owns `ComputeNode` and `InferenceEndpoint`, their immutable
static relationships, locality, trust zone, enabled state, and scoped
observations. Provider protocols, credentials, models, and selection belong
to Cognition Fabric. Mission authority remains in Aquila.

The catalog has no scheduler, discovery daemon, vendor requirement, placement
engine, or workload lifecycle. Operator reconfiguration uses a new catalog
revision; historical selection tuples keep their original meaning.
