"""HTTP boundary and migration checks; synthetic SQLite only, no customer services."""
import unittest
import uuid
from unittest.mock import patch

import httpx
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.main import app


class PreviewBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine(
            "sqlite://", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        self.api_patch = patch("app.main.make_engine", return_value=self.engine)
        self.db_patch = patch("app.database.make_engine", return_value=self.engine)
        self.api_patch.start()
        self.db_patch.start()
        self.lifespan = app.router.lifespan_context(app)
        await self.lifespan.__aenter__()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.lifespan.__aexit__(None, None, None)
        self.api_patch.stop()
        self.db_patch.stop()

    async def test_readiness_requires_migrated_metadata_and_retains_identity(self):
        response = await self.client.get("/api/health/ready")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "not-ready"})
        config = Config("alembic.ini")
        command.upgrade(config, "head")
        first = await self.client.get("/api/health/ready")
        self.assertEqual(first.status_code, 200)
        marker = first.json()["instance_id"]
        self.assertEqual(str(uuid.UUID(marker)), marker)
        command.upgrade(config, "head")
        second = await self.client.get("/api/health/ready")
        self.assertEqual(second.json()["instance_id"], marker)
        command.downgrade(config, "base")
        self.assertEqual((await self.client.get("/api/health/ready")).status_code, 503)

    async def test_admin_denied_for_every_supported_method(self):
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                response = await self.client.request(
                    method, "/api/admin/settings", json={"enabled": True},
                )
                self.assertEqual(response.status_code, 403)

    async def test_only_synthetic_data_and_no_processing_endpoints(self):
        data = (await self.client.get("/api/demo/processes")).json()
        self.assertIs(data["synthetic"], True)
        self.assertEqual(len(data["items"]), 5)
        self.assertTrue(all(row["id"].startswith("DEMO-") for row in data["items"]))
        for path in ("/api/processes", "/api/import", "/api/config"):
            self.assertEqual((await self.client.post(path)).status_code, 404)
        self.assertEqual((await self.client.get("/api/health/live")).status_code, 200)


if __name__ == "__main__":
    unittest.main()
