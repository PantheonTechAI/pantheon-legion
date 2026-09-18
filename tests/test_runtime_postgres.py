import os
import unittest
from unittest import mock

from tests.runtime_postgres import runtime_test_database_url


class RuntimePostgreSQLTestGuardTests(unittest.TestCase):
    def test_requires_explicit_test_url(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "is required"):
                runtime_test_database_url()

    def test_requires_test_suffixed_database(self):
        with mock.patch.dict(
            os.environ,
            {
                "LEGION_RUNTIME_TEST_DATABASE_URL": (
                    "postgresql+psycopg://runtime:secret@localhost/legion_runtime"
                )
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "must end with '_test'"):
                runtime_test_database_url()

    def test_rejects_same_deployed_and_destructive_test_target(self):
        test_url = (
            "postgresql+psycopg://runtime:test-secret@localhost:5432/"
            "legion_runtime_test"
        )
        deployed_url = (
            "postgresql+psycopg://runtime:production-secret@localhost/"
            "legion_runtime_test"
        )
        with mock.patch.dict(
            os.environ,
            {
                "LEGION_RUNTIME_DATABASE_URL": deployed_url,
                "LEGION_RUNTIME_TEST_DATABASE_URL": test_url,
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "targets match"):
                runtime_test_database_url()


if __name__ == "__main__":
    unittest.main()
