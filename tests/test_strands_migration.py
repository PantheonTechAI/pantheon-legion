"""Experimental migration must preserve incumbent data and refuse lossy rollback."""

import os
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config

from tests.runtime_postgres import reset_runtime_database, runtime_test_database_url
from tests import test_strands_spike


class StrandsMigrationTests(unittest.TestCase):
    state = test_strands_spike.StrandsRuntimeTests.state
    delegate = test_strands_spike.StrandsRuntimeTests.delegate

    def setUp(self):
        reset_runtime_database()

    def test_empty_downgrade_upgrade_and_no_metadata_drift(self):
        config = Config("legion_runtime/alembic.ini")
        with patch.dict(os.environ, {"LEGION_RUNTIME_DATABASE_URL": runtime_test_database_url()}):
            try:
                command.downgrade(config, "0004")
            finally:
                command.upgrade(config, "head")
            command.check(config)

    def test_work_item_alone_refuses_lossy_downgrade(self):
        _, state, _ = self.state()
        work = self.delegate(state)
        with patch.dict(os.environ, {"LEGION_RUNTIME_DATABASE_URL": runtime_test_database_url()}):
            with self.assertRaisesRegex(RuntimeError, "cannot downgrade: cognition spike data exists"):
                command.downgrade(Config("legion_runtime/alembic.ini"), "0004")
        retained = state["runtime"].repository.get_work_item(work.work_item_id)
        self.assertEqual(retained, work)
