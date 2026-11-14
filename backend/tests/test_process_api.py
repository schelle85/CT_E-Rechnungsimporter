"""Existing AD/session fixture, real journal projection; no runtime auth bypass."""
import unittest
from app.processing_state import ProcessingStore, metadata as processing_metadata
from app.storage_state import StorageStore, metadata as storage_metadata
import test_preview as security_fixture
import test_process_queries as query_fixture


class ProcessApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await security_fixture.SecurityTests.asyncSetUp(self)
        with self.engine.begin() as connection:
            for metadata in (processing_metadata,storage_metadata):
                for table in reversed(metadata.sorted_tables):
                    connection.execute(table.delete())
        import time
        self.now=[int(time.time())]
        self.store=ProcessingStore(self.engine,clock=lambda:self.now[0])
        self.storage=StorageStore(self.engine,destination_key="d"*64,clock=lambda:self.now[0])

    asyncTearDown=security_fixture.SecurityTests.asyncTearDown
    challenge=security_fixture.SecurityTests.challenge
    headers=security_fixture.SecurityTests.headers
    login=security_fixture.SecurityTests.login
    mail=query_fixture.ProcessQueryTests.mail

    async def test_both_roles_read_real_empty_then_persisted_data(self):
        for role in ("reader","admin"):
            self.assertEqual((await self.login(role)).status_code,200)
            result=await self.client.get("/api/processes")
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.json()["items"],[])
            self.assertFalse(result.json()["synthetic"])
            self.assertEqual(result.headers["cache-control"],"no-store")
            await self.client.post("/api/auth/logout",headers=self.headers())
        key=self.mail()
        await self.login("reader")
        self.assertEqual((await self.client.get("/api/processes")).json()["total"],1)
        self.assertEqual((await self.client.get("/api/processes/stats")).json()["unknown_open"],1)
        self.assertEqual((await self.client.get("/api/unknown")).json()["total"],1)
        detail=await self.client.get("/api/processes/"+key)
        self.assertEqual(detail.status_code,200)
        self.assertEqual(detail.json()["attachments"][0]["name"],"invoice.pdf")
        self.assertEqual((await self.client.get("/api/demo/processes")).status_code,404)

    async def test_sessions_groups_and_read_only_methods_apply_to_every_new_route(self):
        key=self.mail()
        paths=["/api/processes","/api/processes/stats","/api/processes/"+key,"/api/unknown"]
        for path in paths:
            self.assertEqual((await self.client.get(path)).status_code,401)
        await self.login("reader")
        for path in paths:
            self.assertEqual((await self.client.get(path)).status_code,200)
            denied=await self.client.post(path,json={},headers=self.headers())
            self.assertEqual(denied.status_code,403)
        self.directory.rows["2"*32]["attributes"]["memberOf"]=[]
        self.assertEqual((await self.client.get("/api/processes")).status_code,401)

    async def test_bad_filters_and_not_found_are_neutral_without_journal_writes(self):
        key=self.mail()
        before=self.store.get_message(key)
        await self.login()
        for path in ("/api/processes?page_size=1000","/api/processes?state=untrusted",
                     "/api/processes?received_from=secret-invalid-date","/api/unknown?view=deleted"):
            response=await self.client.get(path)
            self.assertEqual(response.status_code,422)
            self.assertEqual(response.headers["cache-control"],"no-store")
            self.assertNotIn("secret-invalid-date",response.text)
        for value in ("a"*64,"not-a-key"):
            self.assertEqual((await self.client.get("/api/processes/"+value)).status_code,404)
        self.assertEqual(self.store.get_message(key),before)
