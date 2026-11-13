import importlib.util
from pathlib import Path
import unittest
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


def migration(name):
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / name
    spec = importlib.util.spec_from_file_location("isolated_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StorageMigrationTests(unittest.TestCase):
    def test_additive_upgrade_twice_preserves_existing_identity_and_tables(self):
        engine = sa.create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        first = migration("001_app_metadata.py")
        security = migration("002_security_configuration.py")
        storage = migration("004_storage_operations.py")
        self.assertEqual(storage.down_revision, "003_graph_actions")
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                first.upgrade()
                security.upgrade()
                before = connection.execute(sa.text("SELECT instance_id FROM app_metadata")).scalar_one()
                existing = {name: sa.inspect(connection).get_columns(name) for name in sa.inspect(connection).get_table_names()}
                storage.upgrade()
                storage.upgrade()
                self.assertEqual(connection.execute(sa.text("SELECT instance_id FROM app_metadata")).scalar_one(), before)
                self.assertEqual(set(sa.inspect(connection).get_table_names()), set(existing) | {"storage_operations"})
                for name, columns in existing.items():
                    self.assertEqual([column["name"] for column in sa.inspect(connection).get_columns(name)],
                                     [column["name"] for column in columns])
                with self.assertRaises(RuntimeError):
                    storage.downgrade()
                self.assertIn("storage_operations", sa.inspect(connection).get_table_names())
