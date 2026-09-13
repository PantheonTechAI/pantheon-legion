# Legion Tabula Retrieval

Tabula is a provider-neutral retrieval boundary. It filters knowledge by
organization, workspace, and Mission scope before matching a query, then
returns provenance-bearing records that can become Scout evidence. The
reference `InMemoryTabula` and durable `SQLiteTabula` share this deterministic
scope and ranking contract; reopening SQLite retains records without relaxing
visibility rules.

`AquilaService.run_tabula_scout` requires both a delegated `READ_KNOWLEDGE`
operation and the existing delegated `READ_MISSION` operation. It retrieves
evidence through Tabula and supplies it to the read-only Scout. This slice has
no knowledge promotion, mutation, vector-store dependency, or public HTTP API.
