"""Actual SQL journals, no external systems or HTTP authorization substitutes."""
from concurrent.futures import ThreadPoolExecutor
import json
import unittest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
import test_process_queries as fixture
from test_storage_migration import migration
from app.errors import AccessError
from app.processing_decisions import DecisionStore
from app.processing_plan import ProcessingError
from app.processing_state import attachments, corrections, controls, findings, messages, retries
from app.schema import metadata as security_metadata, audit
from app.storage_plan import digest
from app.storage_state import operations


class DecisionTests(unittest.TestCase):
    def setUp(self):
        fixture.ProcessQueryTests.setUp(self)
        security_metadata.create_all(self.engine)
        with self.engine.begin() as c:
            c.execute(audit.delete())
            c.execute(controls.insert().values(singleton=1,version=1,preview_enabled=1,retry_enabled=1,actor='fixture',updated_at=0))
        self.decisions=DecisionStore(self.store)

    mail=fixture.ProcessQueryTests.mail
    state=fixture.ProcessQueryTests.state

    def approve(self, key, request_id='approval-1', decision='PDF', **changes):
        row=self.store.get_attachments(key)[0]
        current=json.loads(row['effective_finding'] or '{}')
        values=dict(request_id=request_id,expected_revision=self.store.get_message(key)['revision'],
            finding_revision=row['finding_revision'],finding_key=digest(current),source_sha256=row['raw_sha256'],
            decision=decision,actor='synthetic-admin')
        values.update(changes)
        return self.decisions.approve(row['attachment_key'],**values)

    def close(self, key, owner, revision):
        intent=self.store.prepare_close(key,owner,revision,fixture.FOLDERS)
        self.store.finish_close(key,owner,revision,parent_id=intent['destination_id'],flagged=True,intent_key=intent['intent_key'])

    def retry(self, key, request_id='retry-001'):
        return self.decisions.retry(key,request_id=request_id,expected_revision=self.store.get_message(key)['revision'],actor='synthetic-admin')

    def test_approval_is_explicit_idempotent_and_not_processed_until_effects_close(self):
        key=self.mail()
        first=self.approve(key,decision='ignored')
        self.assertEqual(first['state'],'approved')
        revision=self.store.start_corrections(key)
        self.assertEqual(self.approve(key,decision='ignored',expected_revision=0),{**first,'state':'processing','applied_revision':revision})
        with self.assertRaises(AccessError):self.approve(key,request_id='different',decision='PDF')
        owned=self.store.claim(key)
        self.close(key,owned['owner'],revision)
        self.assertEqual(self.approve(key,decision='ignored',expected_revision=0)['state'],'processed')
        with self.engine.connect() as c:
            self.assertEqual(c.execute(sa.select(sa.func.count()).select_from(audit).where(audit.c.action=='attachment_approve')).scalar_one(),1)

    def test_failed_retry_unknown_approval_and_consumer_share_current_generation(self):
        key=self.mail(specs=[('a1','failed.pdf','failed',None,'processing_classifier_unavailable')])
        original=self.store.get_attachments(key)[0]['original_finding']
        receipt=self.retry(key)
        self.assertEqual(receipt['state'],'requested')
        self.assertIn(key,self.store.due('corrections'))
        self.assertEqual(self.store.get_message(key)['revision'],0)
        revision=self.decisions.consume_retry(key)
        self.assertEqual(revision,1)
        row=self.store.get_attachments(key)[0]
        self.assertIsNone(row['effective_finding'])
        owned=self.store.claim(key)
        self.store.content(key,row['attachment_key'],owned['owner'],revision,byte_size=row['byte_size'],sha256=row['raw_sha256'])
        finding=dict(status='unknown',category=None,reason='ambiguous_pdf',method='pdf_text',format='PDF',
            original_sha256=row['raw_sha256'],rule_version='ap03-4')
        self.store.finding(key,row['attachment_key'],owned['owner'],revision,finding)
        self.close(key,owned['owner'],revision)
        self.assertEqual(self.store.get_attachments(key)[0]['original_finding'],original)
        self.assertTrue(self.queries.detail(key)['attachments'][0]['can_correct'])
        self.approve(key,decision='ignored')
        self.assertEqual(self.store.start_corrections(key),2)
        with self.engine.connect() as c:
            history=c.execute(sa.select(findings).where(findings.c.attachment_key==row['attachment_key'])).mappings().all()
            self.assertEqual({item['revision'] for item in history},{0,1})
        replay=self.decisions.retry(key,request_id='retry-001',expected_revision=0,actor='synthetic-admin')
        self.assertEqual(replay['state'],'processed')
        self.assertEqual(replay['requested_at'],receipt['requested_at'])

    def test_structural_and_technical_findings_cannot_be_approved(self):
        for index,(status,reason) in enumerate([('unknown','ambiguous_hybrid'),('failed','pdf_corrupt')]):
            key=self.mail('m'+str(index),[('a1','document.pdf',status,None,reason)])
            for decision in ('PDF','ignored'):
                with self.assertRaises(AccessError):self.approve(key,decision=decision)
        with self.engine.connect() as c:
            self.assertEqual(c.execute(sa.select(sa.func.count()).select_from(corrections)).scalar_one(),0)

    def test_stale_generation_blocks_consumer_and_rolls_back_revision(self):
        key=self.mail()
        self.approve(key)
        with self.engine.begin() as c:
            c.execute(attachments.update().where(attachments.c.message_key==key).values(finding_revision=1))
        with self.assertRaises(ProcessingError):self.store.start_corrections(key)
        self.assertEqual(self.store.get_message(key)['revision'],0)

    def test_approval_and_retry_do_not_overtake_each_other(self):
        key=self.mail(specs=[('a1','unknown.pdf','unknown',None,'ambiguous_pdf'),
                             ('a2','failed.pdf','failed',None,'processing_classifier_unavailable')])
        unknown=next(row for row in self.store.get_attachments(key) if row['effective_status']=='unknown')
        finding=json.loads(unknown['effective_finding'])
        def approve():
            try:return self.decisions.approve(unknown['attachment_key'],request_id='concurrent-approval',expected_revision=0,
                finding_revision=0,finding_key=digest(finding),source_sha256=unknown['raw_sha256'],decision='PDF',actor='synthetic-admin')
            except AccessError as e:return e.status
        def retry():
            try:return self.retry(key)
            except AccessError as e:return e.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda action:action(),[approve,retry]))
        self.assertEqual(sum(isinstance(result,dict) for result in results),1)
        self.assertIn(409,results)

    def test_current_owner_archive_source_hash_and_payload_conflicts_are_rejected(self):
        key=self.mail()
        for changes in ({'source_sha256':'0'*64},{'finding_key':'0'*64},{'expected_revision':1},{'finding_revision':1}):
            with self.assertRaises(AccessError):self.approve(key,**changes)
        with self.engine.begin() as c:
            c.execute(messages.update().where(messages.c.message_key==key).values(created_at=0))
        with self.assertRaises(AccessError):self.approve(key)
        failed=self.mail('failed',[('a1','failed.pdf','failed',None,'processing_classifier_unavailable')],close=False)
        owned=self.store.claim(failed)
        with self.assertRaises(AccessError):self.retry(failed)
        self.store.release(failed,owned['owner'],0,blocked=True,error='graph_journal_source_changed')
        with self.assertRaises(AccessError):self.retry(failed)

    def test_uncertain_effect_reconciles_same_revision_key_and_attempt_count(self):
        key=self.mail(specs=[('a1','invoice.pdf','recognized','PDF','invoice_fields')],close=False)
        row=self.store.get_attachments(key)[0]
        with self.engine.begin() as c:
            c.execute(attachments.update().where(attachments.c.attachment_key==row['attachment_key']).values(
                storage_state='operator_required',effect_state='blocked'))
            c.execute(messages.update().where(messages.c.message_key==key).values(state='operator_required',error_code='storage_publication_uncertain'))
            c.execute(operations.update().where(operations.c.action_key==row['effect_key']).values(state='operator_required'))
        before=self.storage.get(row['effect_key'])
        self.retry(key)
        self.assertEqual(self.decisions.consume_retry(key),0)
        after=self.store.get_attachments(key)[0]
        self.assertEqual(after['effect_key'],row['effect_key'])
        self.assertEqual(after['effect_state'],'uncertain')
        self.assertEqual(self.storage.get(row['effect_key']),before)
        self.assertEqual(before['publication_attempts'],1)

    def test_settings_are_versioned_audited_and_actually_disable_new_retries(self):
        key=self.mail(specs=[('a1','failed.pdf','failed',None,'processing_classifier_unavailable')])
        self.decisions.save_settings(1,False,False,'synthetic-admin')
        with self.assertRaises(AccessError):self.retry(key)
        with self.assertRaises(AccessError):self.decisions.save_settings(1,True,True,'synthetic-admin')
        self.assertEqual(self.decisions.settings()['version'],2)
        self.assertFalse(self.decisions.settings()['preview_enabled'])

    def test_migration_actual_005_rows_and_receipts_preserved_and_backfilled_once(self):
        engine=sa.create_engine('sqlite://')
        self.addCleanup(engine.dispose)
        with engine.begin() as c:
            with Operations.context(MigrationContext.configure(c)):
                for name in ('001_app_metadata.py','002_security_configuration.py','003_graph_actions.py','004_storage_operations.py','005_processing.py'):
                    migration(name).upgrade()
                marker=c.execute(sa.text('SELECT instance_id FROM app_metadata')).scalar_one()
                cols={col['name'] for col in sa.inspect(c).get_columns('processing_attachments')}
                self.assertNotIn('effective_finding',cols)
                legacy=json.dumps({'status':'failed','category':None,'reason':'processing_io_failed','method':'source_or_handoff'})
                c.execute(sa.text("INSERT INTO processing_messages(message_key,mailbox_key,graph_id,received_at,source_parent,current_parent,manifest_key,state,revision,completed_revision,lease_until,next_attempt,created_at,updated_at) VALUES(:k,:k,'synthetic','2026-12-01T00:00:00+00:00','inbox','failed',:k,'failed',0,0,0,0,1,1)"),{'k':'a'*64})
                c.execute(sa.text("INSERT INTO processing_attachments(attachment_key,message_key,graph_id,source,state,signature,original_finding,effective_status) VALUES(:k,:m,'synthetic','[]','classified',0,:f,'failed')"),{'k':'b'*64,'m':'a'*64,'f':legacy})
                migration('006_processing_web.py').upgrade()
                migration('006_processing_web.py').upgrade()
                self.assertEqual(c.execute(sa.text('SELECT instance_id FROM app_metadata')).scalar_one(),marker)
                row=c.execute(sa.select(attachments)).mappings().one()
                self.assertEqual(row['original_finding'],legacy)
                self.assertEqual(row['effective_finding'],legacy)
                self.assertEqual(row['finding_revision'],0)
                self.assertEqual(c.execute(sa.select(sa.func.count()).select_from(findings)).scalar_one(),1)
                self.assertEqual(c.execute(sa.select(controls.c.version)).scalar_one(),1)
    def test_zero_publication_failure_can_retry_without_changing_effect_identity(self):
        key=self.mail(specs=[('a1','invoice.pdf','recognized','PDF','invoice_fields')])
        row=self.store.get_attachments(key)[0]
        with self.engine.begin() as c:
            c.execute(attachments.update().where(attachments.c.attachment_key==row['attachment_key']).values(storage_state='failed'))
            c.execute(operations.update().where(operations.c.action_key==row['effect_key']).values(
                state='operator_required',publication_attempts=0,owner=None,lease_until=0))
        before=self.storage.get(row['effect_key'])
        self.retry(key)
        self.assertEqual(self.decisions.consume_retry(key),1)
        after=self.storage.get(row['effect_key'])
        self.assertEqual(after['state'],'pending')
        for field in ('action_key','input_key','target','path_key','dedupe_key','publication_attempts'):
            self.assertEqual(after[field],before[field])
        self.assertEqual(self.store.get_attachments(key)[0]['effect_key'],row['effect_key'])

    def test_r1_applied_customer_decision_survives_download_failure_and_retry(self):
        key=self.mail()
        self.approve(key,decision='Mahnung')
        aid=self.store.get_attachments(key)[0]['attachment_key']
        original=self.store.get_attachments(key)[0]['original_finding']
        revision=self.store.start_corrections(key)
        owned=self.store.claim(key)
        self.store.failed(key,aid,owned['owner'],revision,'graph_transport_error')
        self.close(key,owned['owner'],revision)
        self.retry(key)
        revision=self.decisions.consume_retry(key)
        row=self.store.get_attachments(key)[0]
        self.assertEqual((row['effective_status'],row['category']),('recognized','Mahnung'))
        self.assertEqual(row['original_finding'],original)
        self.assertEqual(row['finding_revision'],0)
        owned=self.store.claim(key)
        request=self.store.begin_storage(key,aid,owned['owner'],revision,'query-tests','d'*64)
        receipt=self.storage.claim(request)
        self.storage.begin_publication(request.key,receipt['owner'])
        self.storage.finish(request.key,receipt['owner'],'stored')
        from app.storage import StorageResult
        self.store.stored(key,aid,owned['owner'],revision,StorageResult(request.key,'stored',receipt['target']))
        self.close(key,owned['owner'],revision)
        row=self.queries.detail(key)['attachments'][0]
        self.assertEqual((row['status'],row['category']),('processed','Mahnung'))
        self.assertEqual(row['approval']['state'],'processed')
        self.assertEqual(row['storage_receipt']['publication_attempts'],1)

    def test_r2_open_revision_zero_retry_remains_due_after_interruption_and_delay(self):
        key=self.mail(close=False)
        owned=self.store.claim(key)
        self.store.release(key,owned['owner'],0,blocked=True,error='graph_transport_error')
        self.retry(key)
        self.assertEqual(self.decisions.consume_retry(key),0)
        owned=self.store.claim(key)
        self.store.release(key,owned['owner'],0,delay=10)
        self.assertNotIn(key,self.store.due('corrections'))
        self.now[0]+=10
        self.assertIn(key,self.store.due('corrections'))
        self.assertIsNone(self.decisions.consume_retry(key))
        owned=self.store.claim(key)
        self.assertEqual(owned['revision'],0)
        self.close(key,owned['owner'],0)
        with self.engine.connect() as c:
            records=c.execute(sa.select(retries).where(retries.c.message_key==key)).mappings().all()
        self.assertEqual(len(records),1)
        self.assertEqual((records[0]['state'],records[0]['applied_revision']),('processed',0))
