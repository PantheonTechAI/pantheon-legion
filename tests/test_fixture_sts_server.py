import json
import unittest
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
from uuid import uuid4

from tests.federation.fixture_server import FixtureSTSServer


def _claims():
    now = datetime.now(timezone.utc)
    return {
        "schema_version": "1.0", "assertion_id": str(uuid4()), "issuer": "aquila", "audience": "pantheon-sts",
        "subject_id": "fixture-scout", "actor_id": "aquila", "mission_id": str(uuid4()),
        "organization_id": str(uuid4()), "workspace_id": str(uuid4()), "target_product": "TABULA",
        "target_audience": "pantheon-tabula-mcp", "operation": "TABULA_CORPUS_READ",
        "binding_id": str(uuid4()), "binding_version": "1.0.0", "correlation_id": str(uuid4()),
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
    }


class FixtureSTSServerTests(unittest.TestCase):
    def test_issues_token_over_wsgi_and_exposes_tabula_introspection(self):
        with FixtureSTSServer() as fixture:
            token = fixture.issue_token(_claims())
            request = Request(
                fixture.introspection_url, data=json.dumps({"token": token}).encode(), method="POST",
                headers={"Content-Type": "application/json", "X-Pantheon-Service": "tabula"},
            )
            with urlopen(request) as response:
                payload = json.loads(response.read().decode())
        self.assertTrue(payload["active"])
        self.assertEqual(payload["operation"], "TABULA_CORPUS_READ")
        self.assertTrue(token.startswith("pts_"))

    def test_docker_url_requires_explicit_all_interface_binding(self):
        with FixtureSTSServer() as fixture:
            with self.assertRaisesRegex(RuntimeError, "0.0.0.0"):
                _ = fixture.docker_introspection_url
        with FixtureSTSServer(host="0.0.0.0") as fixture:
            self.assertTrue(fixture.docker_introspection_url.startswith("http://host.docker.internal:"))
            self.assertTrue(fixture.issue_token(_claims()).startswith("pts_"))


if __name__ == "__main__":
    unittest.main()
