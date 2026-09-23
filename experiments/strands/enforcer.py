"""Independent fixture boundary: no worker callback or hook grants authority."""

import sqlite3
from uuid import uuid4

from aquila_api.spike_actions import action_digest
from legion_kernel import AuthorizationError


class ReviewMarkerFixture:
    def __init__(self, *, database, authority, gate, current_scope):
        self.connection = sqlite3.connect(database)
        self.connection.row_factory = sqlite3.Row
        self.authority, self.gate, self.current_scope = authority, gate, current_scope
        with self.connection:
            self.connection.execute("""CREATE TABLE IF NOT EXISTS review_markers (
                logical_operation_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL,
                action_digest TEXT NOT NULL, marker TEXT NOT NULL CHECK(marker='reviewed'),
                receipt_id TEXT NOT NULL UNIQUE)""")

    def close(self):
        self.connection.close()

    def dispatch(self, permit_id, arguments):
        digest = action_digest(arguments)
        with self.gate:
            # Authenticated binding and fence are independently obtained here;
            # no caller can supply a different identity or successful hook flag.
            scope = self.current_scope()
            mode = self.authority.consume(permit_id, scope, arguments)
            with self.connection:
                row = self.connection.execute("SELECT * FROM review_markers WHERE logical_operation_id=?",
                                              (scope.logical_operation_id,)).fetchone()
                if row:
                    if row["mission_id"] != scope.mission_id or row["action_digest"] != digest:
                        raise AuthorizationError("SPIKE_EFFECT_SCOPE_MISMATCH")
                    receipt_id = row["receipt_id"]
                elif mode == "RECONCILE":
                    raise AuthorizationError("SPIKE_EFFECT_RECEIPT_MISSING")
                else:
                    receipt_id = str(uuid4())
                    self.connection.execute("INSERT INTO review_markers VALUES (?, ?, ?, ?, ?)",
                        (scope.logical_operation_id, scope.mission_id, digest, "reviewed", receipt_id))
            # A crash here leaves the ledger receipt authoritative for the effect.
            # A replacement requires a fresh permit, then returns that receipt.
            self.after_commit()
            self.authority.record_receipt(permit_id, scope, arguments, receipt_id)
            return receipt_id

    def after_commit(self):
        """Test fault-injection seam, outside the atomic marker/receipt commit."""
