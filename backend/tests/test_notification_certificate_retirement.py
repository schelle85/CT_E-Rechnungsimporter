"""B2 regressions: actual store gates and certificate proofs, synthetic transport only."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import uuid4
import sqlalchemy as sa
from app.notification_certificate import CERTIFICATE_TOKEN,record_certificate
from app.notification_model import NotificationError,certificate_slot
from app.notification_schema007 import outbox
from notification_test_support import Fixture,SCOPE,material


class CertificateRetirementTests(Fixture,unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.configure(daily_enabled=False,weekly_enabled=False,certificate_time="00:00")

    def snapshot(self,certificate):
        value=self.service(certificate).observe()
        warning=value["warning"]
        return (certificate_slot(SCOPE,warning,self.now[0],self.config),
            dict(fingerprint=warning["fingerprint"],expires_at=warning["expires_at"],
                remaining_seconds=warning["expires_at"]-self.now[0]))

    def prepare(self,snapshot):
        slot,facts=snapshot
        return self.store.prepare(slot,SCOPE,facts,expected_version=1,as_of=self.now[0])

    def reserve(self,row):
        ticket=self.store.claim(row["slot_key"],SCOPE)
        self.assertIsNotNone(ticket)
        self.assertTrue(self.store.reserve(ticket,budget=self.budget()))
        return ticket

    def proof(self,certificate,revision):
        return record_certificate(self.store,SCOPE,certificate.metadata(self.now[0]),expected_revision=revision,
            fresh_proof=dict(fingerprint=certificate.fingerprint,scope_key=SCOPE,at=self.now[0]))

    def raw(self,key):
        with self.engine.connect() as c:
            return dict(c.execute(sa.select(outbox).where(outbox.c.slot_key==key)).mappings().one())

    def test_original_late_first_prepare_after_successor_proof_is_blocked(self):
        old=material(days=2);successor=material(days=30)
        delayed=self.service(old)
        configuration=self.store.configuration
        closed=[]
        def interleave():
            if not closed:
                value=self.service(successor).observe(probe=True)
                self.assertIsNone(value["warning"])
                self.assertEqual(value["last_closed"]["fingerprint"],old.fingerprint)
                closed.append(self.store.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN))
            return configuration()
        with patch.object(self.store,"configuration",side_effect=interleave):
            with self.assertRaises(NotificationError) as error:delayed.plan()
        self.assertEqual(error.exception.code,"notification_certificate_series_closed")
        self.assertEqual(self.store.history(SCOPE)["total"],0)
        self.assertEqual(self.store.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN),closed[0])
        self.assertEqual(sum(r.method=="POST" for r in self.http_calls),0)

    def test_existing_unreserved_old_plan_cannot_be_replanned_or_reserved(self):
        snapshot=self.snapshot(material(days=2));row=self.prepare(snapshot)
        ticket=self.store.claim(row["slot_key"],SCOPE)
        self.service(material(days=30)).observe(probe=True)
        before=self.raw(row["slot_key"])
        with self.assertRaises(NotificationError):self.prepare(snapshot)
        self.assertEqual(self.raw(row["slot_key"]),before)
        self.assertEqual((before["state"],before["reservations"]),("obsolete",0))
        self.assertFalse(self.store.reserve(ticket,budget=self.budget()))
        self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))

    def test_reserved_old_plan_without_post_gate_is_rejected_without_reset(self):
        row=self.prepare(self.snapshot(material(days=2)));ticket=self.reserve(row)
        before=self.raw(row["slot_key"])
        self.service(material(days=30)).observe(probe=True)
        after=self.raw(row["slot_key"])
        self.assertEqual((after["state"],after["reservations"],after["post_started_at"]),("rejected",1,None))
        for name in ("reserved_at","payload_cipher","payload_hash","plan_revision","monitor_keys"):
            self.assertEqual(after[name],before[name])
        self.assertIsNone(self.store.begin_post(ticket,budget=self.budget()))
        self.assertFalse(self.store.reserve(ticket,budget=self.budget()))
        self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))
        self.assertEqual(sum(r.method=="POST" for r in self.http_calls),0)

    def test_post_gate_winning_before_proof_preserves_once_and_terminal_history(self):
        for terminal in ("accepted","unknown"):
            with self.subTest(terminal=terminal):
                self.now[0]+=3601
                row=self.prepare(self.snapshot(material(days=2)));ticket=self.reserve(row)
                self.assertIsNotNone(self.store.begin_post(ticket,budget=self.budget()))
                self.service(material(days=30)).observe(probe=True)
                self.assertEqual(self.store.read(row["slot_key"])["state"],"sending")
                result=self.store.finish(ticket,terminal,http_status=202 if terminal=="accepted" else None)
                self.service(material(days=30)).observe(probe=True)
                self.assertEqual(self.store.read(row["slot_key"]),result)
                self.assertIsNone(self.store.begin_post(ticket,budget=self.budget()))
                self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))
                self.assertEqual(result["reservations"],1)

    def test_file_swap_without_valid_proof_keeps_original_warning_sendable(self):
        old=material(days=2)
        row=self.prepare(self.snapshot(old))
        original=self.store.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN)["data"]["warning"]
        # A future-dated certificate can authenticate in the transport double but is
        # locally invalid, so that GET success is not a successor retirement proof.
        result=self.service(material(days=30,before=1)).send(row["slot_key"],budget=self.budget(),owner=uuid4().hex)
        self.assertEqual(result["state"],"accepted")
        current=self.store.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN)["data"]
        self.assertEqual(current["warning"],original)
        self.assertIsNone(current["proof"])
        posts=[r for r in self.http_calls if r.method=="POST"]
        self.assertEqual(len(posts),1)
        self.assertIn(old.fingerprint,json.loads(posts[0].content)["message"]["body"]["content"])

    def test_forged_series_scope_expiry_or_fixed_facts_do_not_create_a_plan(self):
        slot,facts=self.snapshot(material(days=2))
        before=self.store.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN)
        cases=[(replace(slot,scope_key="b"*64),facts),
            (replace(slot,series_id=uuid4().hex),facts),
            (replace(slot,expires_at=slot.expires_at+1),dict(facts,expires_at=slot.expires_at+1,remaining_seconds=facts["remaining_seconds"]+1)),
            (replace(slot,fingerprint="a"*64,tag="a"*64),dict(facts,fingerprint="a"*64)),
            (slot,dict(facts,remaining_seconds=facts["remaining_seconds"]+1))]
        for snapshot in cases:
            with self.subTest(snapshot=snapshot):
                with self.assertRaises(NotificationError):self.prepare(snapshot)
        self.assertEqual(self.store.history(SCOPE)["total"],0)
        self.assertEqual(self.store.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN),before)

    def test_same_fingerprint_reopened_in_same_second_does_not_adopt_old_series(self):
        old=material(days=2);snapshot=self.snapshot(old)
        self.service(material(days=30)).observe(probe=True)
        reopened=self.snapshot(old)
        self.assertEqual(snapshot[0].started_at,reopened[0].started_at)
        self.assertNotEqual(snapshot[0].series_id,reopened[0].series_id)
        self.assertEqual(snapshot[0].key(self.store.instance,SCOPE),reopened[0].key(self.store.instance,SCOPE))
        with self.assertRaises(NotificationError):self.prepare(snapshot)
        row=self.prepare(reopened)
        self.assertEqual(row["reservations"],0)
        ticket=self.reserve(row)
        self.assertIsNotNone(self.store.begin_post(ticket,budget=self.budget()))

    def test_reserved_schedule_stays_frozen_while_series_remains_open(self):
        row=self.prepare(self.snapshot(material(days=2)));ticket=self.reserve(row)
        self.configure(certificate_time="23:59",recipients=["changed@example.invalid"])
        payload=self.store.begin_post(ticket,budget=self.budget())
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["message"]["toRecipients"]),2)

    def test_persisted_old_binding_is_checked_independently_at_both_gates(self):
        for gate in ("reserve","begin_post"):
            with self.subTest(gate=gate):
                self.now[0]+=3601
                row=self.prepare(self.snapshot(material(days=2)))
                ticket=self.store.claim(row["slot_key"],SCOPE)
                if gate=="begin_post":self.assertTrue(self.store.reserve(ticket,budget=self.budget()))
                before=self.raw(row["slot_key"])
                self.service(material(days=30)).observe(probe=True)
                # Fault injection: restore only the pre-cleanup row lifecycle fields.
                # The real valid proof and CLOSED monitor remain authoritative. This
                # verifies each gate, rather than relying on the eager bulk cleanup.
                with self.engine.begin() as c:
                    c.execute(outbox.update().where(outbox.c.slot_key==row["slot_key"]).values(
                        **{name:before[name] for name in ("state","owner","lease_until","error_code","completed_at")}))
                result=getattr(self.store,gate)(ticket,budget=self.budget())
                self.assertFalse(result)
                after=self.raw(row["slot_key"])
                self.assertEqual(after["state"],"rejected" if gate=="begin_post" else "obsolete")
                for name in ("reservations","reserved_at","post_started_at","payload_cipher","payload_hash","monitor_keys"):
                    self.assertEqual(after[name],before[name])
                self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))
        self.assertEqual(sum(r.method=="POST" for r in self.http_calls),0)

    def test_atomic_proof_against_reservation_and_post_gate(self):
        for gate in ("reserve","begin_post"):
            for iteration in range(3):
                with self.subTest(gate=gate,iteration=iteration):
                    self.now[0]+=3601
                    row=self.prepare(self.snapshot(material(days=2)))
                    ticket=self.store.claim(row["slot_key"],SCOPE)
                    if gate=="begin_post":self.assertTrue(self.store.reserve(ticket,budget=self.budget()))
                    successor=material(days=30)
                    revision=self.store.monitor_state(SCOPE,"certificate",CERTIFICATE_TOKEN)["revision"]
                    barrier=Barrier(2)
                    def attempt():
                        barrier.wait(timeout=5)
                        return getattr(self.store,gate)(ticket,budget=self.budget())
                    def retire():
                        barrier.wait(timeout=5)
                        return self.proof(successor,revision)
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        pending=pool.submit(attempt);proof=pool.submit(retire)
                        permission=pending.result(timeout=10)
                        self.assertIsNone(proof.result(timeout=10)["warning"])
                    final=self.store.read(row["slot_key"])
                    if gate=="begin_post" and permission is not None:
                        self.assertEqual((final["state"],final["reservations"]),("sending",1))
                        self.assertIsNotNone(final["post_started_at"])
                        self.store.finish(ticket,"unknown")
                    else:
                        self.assertIsNone(final["post_started_at"])
                        self.assertEqual(final["state"],"rejected" if final["reservations"] else "obsolete")
                    self.assertIsNone(self.store.begin_post(ticket,budget=self.budget()))
                    self.assertIsNone(self.store.claim(row["slot_key"],SCOPE))
        self.assertEqual(self.http_calls,[])
