"""Transactional web intents. No Graph calls, file writes, classifier or scheduler."""
import json
import sqlalchemy as sa
from app.errors import AccessError
from app.process_queries import archive_boundary, key_value
from app.processing_plan import checked_finding, correction_allowed, ProcessingError
from app.processing_state import attachments, corrections, controls, encoded, findings, messages, retries
from app.schema import audit
from app.storage_plan import digest
from app.storage_state import operations

IDENTITY_ERRORS = {'graph_before_cutoff','graph_journal_identity_invalid','graph_journal_parent_invalid',
    'graph_journal_source_changed','graph_journal_manifest_changed','graph_identity_changed',
    'graph_inbox_changed','graph_destination_changed','processing_content_changed','processing_source_conflict'}


def log(connection, actor, action, now, key):
    connection.execute(audit.insert().values(occurred_at=int(now),actor=actor[:256],action=action,result='ok',
        changed_fields=encoded([key]),config_id=None))


def retry_plan(connection, message, rows, now, *, lock=False):
    """A bounded retry preserves every existing effect key, receipt and attempt count."""
    if (message['created_at'] < archive_boundary(now) or message['owner'] and message['lease_until'] > now
            or message['error_code'] in IDENTITY_ERRORS):
        return None
    query=sa.select(corrections.c.correction_key).where(
        corrections.c.message_key==message['message_key'],corrections.c.state=='approved')
    if connection.execute(query.with_for_update() if lock else query).first():
        return None
    if message['completed_revision'] < message['revision']:
        if message['state']!='operator_required' and not message['error_code']:
            return None
        # Existing uncertain close/publication intents must reconcile in the same revision.
        return {'mode':'resume','actions':[]}
    actions=[]
    for row in rows:
        if row['error_code'] in IDENTITY_ERRORS:
            return None
        if row['effective_status']=='failed' and not row['effect_key'] and json.loads(row['source'])[5]=='file':
            query=sa.select(corrections).where(corrections.c.attachment_key==row['attachment_key'])
            approved=connection.execute(query.with_for_update() if lock else query).mappings().first()
            if approved:
                if approved['applied_revision'] is None or approved['state'] not in {'processing','failed'} or approved['decision']=='ignored':
                    return None
                actions.append([row['attachment_key'],'decision'])
            else:
                actions.append([row['attachment_key'],'classify'])
        elif row['storage_state']=='failed' and row['effective_status']=='recognized' and row['effect_key'] and row['effect_payload']:
            query=sa.select(operations).where(operations.c.action_key==row['effect_key'])
            receipt=connection.execute(query.with_for_update() if lock else query).mappings().first()
            if receipt and (receipt['state'] not in {'pending','operator_required'} or receipt['publication_attempts']!=0
                    or receipt['owner'] and receipt['lease_until']>now):
                return None
            actions.append([row['attachment_key'],'storage'])
        elif row['effect_key'] and row['effect_state']!='done':
            return None
    return {'mode':'new','actions':sorted(actions)} if actions else None


def correction_receipt(row):
    return {name:row[name] for name in ('correction_key','attachment_key','decision','approved_by','approved_at','state','applied_revision')}


def retry_receipt(row):
    return {name:row[name] for name in ('request_key','message_key','expected_revision','previous_state','actor',
        'requested_at','state','applied_revision','finished_at','error_code')}


class DecisionStore:
    def __init__(self, processing):
        self.processing=processing
        self.engine,self.clock=processing.engine,processing.clock

    @staticmethod
    def _controls(connection, *, lock=False):
        query=sa.select(controls).where(controls.c.singleton==1)
        row=connection.execute(query.with_for_update() if lock else query).mappings().first()
        if row is None:raise AccessError(503,'Verarbeitungseinstellungen noch nicht bereit.')
        return dict(row)

    def settings(self):
        with self.engine.connect() as connection:
            row=self._controls(connection)
            return {'version':row['version'],'preview_enabled':bool(row['preview_enabled']),
                    'retry_enabled':bool(row['retry_enabled']),'actor':row['actor'],'updated_at':row['updated_at']}

    def save_settings(self, expected_version, preview_enabled, retry_enabled, actor):
        now=int(self.clock())
        with self.processing.decision_transaction() as connection:
            current=self._controls(connection,lock=True)
            if expected_version!=current['version']:raise AccessError(409,'Einstellungen wurden zwischenzeitlich geändert.')
            changed=connection.execute(controls.update().where(controls.c.singleton==1,controls.c.version==expected_version).values(
                version=expected_version+1,preview_enabled=int(preview_enabled),retry_enabled=int(retry_enabled),actor=actor,updated_at=now))
            if changed.rowcount!=1:raise AccessError(409,'Einstellungen wurden zwischenzeitlich geändert.')
            log(connection,actor,'processing_controls',now,str(expected_version+1))
            return {'version':expected_version+1,'preview_enabled':preview_enabled,'retry_enabled':retry_enabled,
                    'actor':actor,'updated_at':now}

    def approve(self, key, *, request_id, expected_revision, finding_revision, finding_key, source_sha256, decision, actor):
        key_value(key)
        payload=digest([expected_revision,finding_revision,finding_key,source_sha256,decision,actor])
        request_key=digest([key,request_id])
        now=int(self.clock())
        # Immutable FK lookup is outside the decision transaction: it cannot create
        # a REPEATABLE READ snapshot before waiting for the mail's exclusive lock.
        with self.engine.connect() as lookup:
            raw=lookup.execute(sa.select(attachments.c.message_key).where(attachments.c.attachment_key==key)).first()
        if raw is None:raise AccessError(404,'Anhang nicht vorhanden.')
        with self.processing.decision_transaction() as connection:
            message=self.processing._message(connection,raw[0])
            row=self.processing._attachment(connection,raw[0],key)
            previous=connection.execute(sa.select(corrections).where(corrections.c.correction_key==request_key).with_for_update()).mappings().first()
            if previous:
                if previous['request_payload']!=payload:raise AccessError(409,'Anforderung widerspricht dem vorhandenen Beleg.')
                return correction_receipt(previous)
            if connection.execute(sa.select(corrections.c.correction_key).where(corrections.c.attachment_key==key).with_for_update()).first():
                raise AccessError(409,'Für diesen Anhang liegt bereits eine Freigabe vor.')
            current=json.loads(row['effective_finding'] or row['original_finding'] or '{}')
            try:checked_finding(current,row['raw_sha256'])
            except ProcessingError:raise AccessError(409,'Aktueller Befund erlaubt keine Zuordnung.') from None
            if (decision not in {'PDF','Zahlungsavis','Mahnung','ignored'} or message['revision']!=expected_revision
                    or message['completed_revision']!=expected_revision or message['owner']
                    or message['state'] not in {'waiting_correction','done','failed'}
                    or message['created_at']<archive_boundary(now) or row['effective_status']!='unknown'
                    or not correction_allowed(current) or row['effect_key'] or row['raw_sha256']!=source_sha256
                    or row['finding_revision']!=finding_revision or digest(current)!=finding_key):
                raise AccessError(409,'Vorgang oder Befund wurde geändert; bitte neu laden.')
            if connection.execute(sa.select(retries.c.request_key).where(retries.c.message_key==raw[0],retries.c.state=='requested').with_for_update()).first():
                raise AccessError(409,'Für diesen Vorgang ist bereits eine Wiederholung freigegeben.')
            values=dict(correction_key=request_key,attachment_key=key,message_key=raw[0],expected_finding=finding_key,
                expected_revision=finding_revision,request_payload=payload,decision=decision,approved_by=actor,approved_at=now,
                state='approved',applied_revision=None)
            connection.execute(corrections.insert().values(**values))
            log(connection,actor,'attachment_approve',now,request_key)
            return correction_receipt(values)

    def retry(self, key, *, request_id, expected_revision, actor):
        key_value(key)
        payload=digest([expected_revision,actor])
        request_key=digest([key,request_id])
        now=int(self.clock())
        with self.processing.decision_transaction() as connection:
            raw=connection.execute(sa.select(messages).where(messages.c.message_key==key).with_for_update()).mappings().first()
            if raw is None:raise AccessError(404,'Vorgang nicht vorhanden.')
            message=dict(raw)
            previous=connection.execute(sa.select(retries).where(retries.c.request_key==request_key).with_for_update()).mappings().first()
            if previous:
                if previous['request_payload']!=payload:raise AccessError(409,'Anforderung widerspricht dem vorhandenen Beleg.')
                return retry_receipt(previous)
            if not self._controls(connection,lock=True)['retry_enabled']:raise AccessError(409,'Technische Wiederholung ist deaktiviert.')
            if message['revision']!=expected_revision:raise AccessError(409,'Vorgang wurde geändert; bitte neu laden.')
            if connection.execute(sa.select(retries.c.request_key).where(retries.c.message_key==key,retries.c.state=='requested').with_for_update()).first():
                raise AccessError(409,'Für diesen Vorgang ist bereits eine Wiederholung freigegeben.')
            rows=[dict(row) for row in connection.execute(sa.select(attachments).where(attachments.c.message_key==key).with_for_update()).mappings()]
            plan=retry_plan(connection,message,rows,now,lock=True)
            if plan is None:raise AccessError(409,'Dieser Zustand erlaubt keine sichere technische Wiederholung.')
            values=dict(request_key=request_key,message_key=key,request_payload=payload,expected_revision=expected_revision,
                plan=encoded(plan),previous_state=message['state'],actor=actor,requested_at=now,state='requested',
                applied_revision=None,finished_at=None,error_code=None)
            connection.execute(retries.insert().values(**values))
            log(connection,actor,'processing_retry_request',now,request_key)
            return retry_receipt(values)

    def consume_retry(self, key):
        now=int(self.clock())
        with self.processing.decision_transaction() as connection:
            message=self.processing._message(connection,key)
            request=connection.execute(sa.select(retries).where(retries.c.message_key==key,retries.c.state=='requested').with_for_update()).mappings().first()
            if request is None:return None
            rows=[dict(row) for row in connection.execute(sa.select(attachments).where(attachments.c.message_key==key).with_for_update()).mappings()]
            plan=retry_plan(connection,message,rows,now,lock=True)
            if message['revision']!=request['expected_revision'] or plan is None or encoded(plan)!=request['plan']:
                connection.execute(retries.update().where(retries.c.request_key==request['request_key']).values(
                    state='failed',finished_at=now,error_code='processing_retry_stale'))
                log(connection,request['actor'],'processing_retry_rejected',now,request['request_key'])
                return None
            revision=message['revision']+(plan['mode']=='new')
            changes=dict(revision=revision,owner=None,lease_until=0,state='processing',error_code=None,next_attempt=now,updated_at=now)
            if plan['mode']=='new':changes.update(close_key=None,close_payload=None,state='registered')
            elif message['close_key']:changes['state']='closing'
            connection.execute(messages.update().where(messages.c.message_key==key).values(**changes))
            for aid,action in plan['actions']:
                if action=='classify':
                    values=dict(effective_finding=None,effective_status=None,category=None,state='pending',finding_revision=revision,
                        class_owner=None,class_revision=None,error_code=None)
                elif action=='decision':
                    approved=connection.execute(sa.select(corrections).where(corrections.c.attachment_key==aid).with_for_update()).mappings().one()
                    values=dict(effective_status='recognized',category=approved['decision'],state='classified',
                        class_owner=None,class_revision=None,error_code=None)
                    connection.execute(corrections.update().where(corrections.c.correction_key==approved['correction_key']).values(
                        state='processing',applied_revision=revision))
                    log(connection,approved['approved_by'],'attachment_correction_resume',now,approved['correction_key'])
                else:
                    values=dict(storage_state=None,effect_state='reserved',error_code=None)
                    row=next(row for row in rows if row['attachment_key']==aid)
                    connection.execute(operations.update().where(operations.c.action_key==row['effect_key'],
                        operations.c.publication_attempts==0,operations.c.state.in_(['pending','operator_required'])).values(
                            state='pending',owner=None,lease_until=0,error_code=None,updated_at=now))
                connection.execute(attachments.update().where(attachments.c.attachment_key==aid).values(**values))
            if plan['mode']=='resume':
                connection.execute(attachments.update().where(attachments.c.message_key==key,attachments.c.effect_state=='blocked').values(effect_state='uncertain'))
            connection.execute(retries.update().where(retries.c.request_key==request['request_key']).values(state='processing',applied_revision=revision))
            log(connection,request['actor'],'processing_retry_consume',now,request['request_key'])
            return revision