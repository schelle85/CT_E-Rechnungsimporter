"""AP08 V1/V3: synthetic queue, transport doubles and one original budget."""
import time
import unittest
from unittest.mock import patch
from uuid import uuid4
import sqlalchemy as sa
from app.notification_cli import arguments
from app.notification_model import NotificationError,OperationBudget,REPORT_FIELDS,Slot
from app.notification_process import execute_notification
from app.notification_runtime import run_job
from app.notification_schema007 import outbox
from notification_test_support import Fixture,CONFIG,SCOPE,material


class AutomaticSelectionTests(Fixture,unittest.TestCase):
    def automatic_row(self,index):
        now=self.now[0]
        return self.store.prepare(Slot("daily",now-86400,now-3600,now-100+index,now+3600,str(index)),
            SCOPE,{key:0 for key in REPORT_FIELDS},expected_version=self.store.configuration()["version"],as_of=now)

    def test_mixed_queue_filters_before_limits_one_and_five_without_mutation(self):
        self.configure(daily_enabled=True)
        test_keys=[]
        for actor in ("operator","ad:"+"1"*32):
            test_keys.append(self.store.request_test(str(uuid4()),self.store.configuration()["version"],SCOPE,actor)["slot_key"])
            self.now[0]+=300  # Keep the actual shared test cooldown intact.
        rows=[self.automatic_row(i)["slot_key"] for i in range(10)]
        with self.engine.begin() as c:
            c.execute(outbox.update().where(outbox.c.slot_key.in_(test_keys)).values(due_at=self.now[0]-1000))
            for index,values in enumerate((dict(not_before=self.now[0]+300),dict(owner="a"*32,lease_until=self.now[0]+300),
                    dict(config_version=0),dict(payload_cipher=None),dict(stale_at=self.now[0]-1))):
                c.execute(outbox.update().where(outbox.c.slot_key==rows[index]).values(**values))
            before=list(c.execute(sa.select(outbox)).mappings())
        self.assertEqual(self.store.pending(SCOPE,limit=1),rows[5:6])
        self.assertEqual(self.store.pending(SCOPE,limit=5),rows[5:])
        with self.engine.connect() as c:self.assertEqual(list(c.execute(sa.select(outbox)).mappings()),before)
        self.now[0]+=301
        self.assertEqual(self.store.pending(SCOPE,limit=1),rows[:1])

    def test_explicit_named_test_still_sends_once_but_is_never_pending(self):
        self.configure()
        key=self.request_row()["slot_key"]
        self.assertEqual(self.store.pending(SCOPE,limit=5),[])
        result=self.service(material()).send(key,budget=self.budget(),owner=uuid4().hex)
        self.assertEqual((result["state"],result["reservations"]),("accepted",1))
        self.assertIsNone(self.store.claim(key,SCOPE))
        self.assertEqual(sum(request.method=="POST" for request in self.http_calls),1)

    def test_automatic_send_rechecks_all_selected_kinds_before_material_or_transport(self):
        self.configure(daily_enabled=True)
        auto=self.automatic_row(0)["slot_key"]
        key=self.request_row()["slot_key"]
        for keys in ([key],[auto,auto,auto,auto,key],[auto,key]):
            # Distinct allowed rows ensure the five-row guard reaches the test kind.
            if len(keys)==5:keys=[self.automatic_row(i+1)["slot_key"] for i in range(4)]+[key]
            with self.subTest(limit=len(keys)),patch("app.notification_runtime.make_engine",return_value=self.engine),\
                    patch("app.notification_runtime.GraphConfig.load",return_value=CONFIG),\
                    patch("app.notification_runtime.load_notification_cipher",return_value=self.cipher),\
                    patch("app.notification_runtime.NotificationStore",return_value=self.store),\
                    patch("app.notification_runtime.CertificateMaterial.load") as certificate:
                with self.assertRaises(NotificationError) as caught:
                    run_job(dict(command="send-automatic",keys=keys,owner="a"*32,deadline=time.monotonic()+50))
                self.assertEqual(caught.exception.code,"notification_automatic_kind_invalid")
                certificate.assert_not_called()
        self.assertEqual(self.store.read(key)["reservations"],0)
        self.assertEqual(self.http_calls,[])


class AutomaticBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_plan_pending_single_send_and_readback_share_original_eighty_seconds(self):
        now=[100.0];calls=[];key="a"*64
        budget=OperationBudget(clock=lambda:now[0])
        async def runner(job,*,deadline):
            calls.append((job,deadline))
            self.assertLessEqual(deadline,budget.deadline)
            if job["command"]=="plan":now[0]+=35;return dict(ok=True),True
            if job["command"]=="pending":return dict(ok=True,keys=[key]),True
            if job["command"]=="send-automatic":now[0]+=25;return None,True
            return dict(ok=True,receipts=[dict(state="unknown",reservations=1)]),True
        with patch("app.notification_process.time.monotonic",side_effect=lambda:now[0]):
            result=await execute_notification(dict(command="automatic"),budget=budget,runner=runner)
        self.assertEqual([item[0]["command"] for item in calls],["plan","pending","send-automatic","readback"])
        self.assertEqual(calls[1][0]["limit"],1)
        self.assertEqual(calls[2][0]["keys"],[key])
        self.assertEqual(calls[2][1],170)
        self.assertFalse(result["ok"]);self.assertTrue(result["persisted"])
        self.assertEqual(budget.deadline,180)

    async def test_late_plan_and_unstopped_selector_cannot_start_send(self):
        for late in (True,False):
            now=[100.0];calls=[];budget=OperationBudget(clock=lambda:now[0])
            async def runner(job,*,deadline):
                calls.append(job["command"])
                if job["command"]=="plan":
                    if late:now[0]+=80
                    return dict(ok=True),True
                return dict(ok=True,keys=["a"*64]),False
            with patch("app.notification_process.time.monotonic",side_effect=lambda:now[0]):
                result=await execute_notification(dict(command="automatic"),budget=budget,runner=runner)
            self.assertFalse(result["persisted"])
            self.assertEqual(calls,["plan"] if late else ["plan","pending"])

    async def test_selector_cannot_expand_single_automatic_dispatch(self):
        calls=[]
        async def runner(job,*,deadline):
            calls.append(job["command"])
            return (dict(ok=True,keys=["a"*64,"b"*64]) if job["command"]=="pending" else dict(ok=True)),True
        with self.assertRaises(NotificationError):
            await execute_notification(dict(command="automatic"),budget=OperationBudget(clock=time.monotonic),runner=runner)
        self.assertEqual(calls,["plan","pending"])
        self.assertEqual(arguments(["automatic","--limit","5","--slot-key","a"*64]),dict(command="automatic"))


class AutomaticDispatchTests(Fixture,unittest.IsolatedAsyncioTestCase):
    async def test_real_dispatch_accepts_report_and_preserves_earlier_prepared_test(self):
        self.configure(daily_enabled=True)
        test=self.request_row()["slot_key"]
        report=AutomaticSelectionTests.automatic_row(self,0)["slot_key"]
        commands=[]
        async def runner(job,*,deadline):
            commands.append(job["command"])
            return run_job(dict(job,deadline=deadline)),True
        certificate=material()
        with patch("app.notification_runtime.make_engine",return_value=self.engine),\
                patch("app.notification_runtime.GraphConfig.load",return_value=CONFIG),\
                patch("app.notification_runtime.load_notification_cipher",return_value=self.cipher),\
                patch("app.notification_runtime.NotificationStore",return_value=self.store),\
                patch("app.notification_runtime.CertificateMaterial.load",return_value=certificate),\
                patch("app.notification_runtime.NotificationService",side_effect=lambda store,config,mat,**kw:self.service(mat)):
            result=await execute_notification(dict(command="dispatch",limit=1),
                budget=OperationBudget(clock=time.monotonic),runner=runner)
        self.assertTrue(result["ok"]);self.assertTrue(result["persisted"])
        self.assertEqual(commands,["pending","send-automatic","readback"])
        self.assertEqual(self.store.read(report)["state"],"accepted")
        self.assertEqual((self.store.read(test)["state"],self.store.read(test)["reservations"]),("prepared",0))
        self.assertEqual(sum(request.method=="POST" for request in self.http_calls),1)
