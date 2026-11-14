"""Explicit isolated test server: synthetic directory/Graph, private RO PDF input, private SQLite.

Only present in the test image; production app.main never imports this module.
No customer DB, LDAP, Graph credentials, CIFS binding or scheduled processing.
"""
import contextlib
from datetime import datetime,timezone
import hashlib
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from app.main import create_app
from pydantic import BaseModel
from typing import Literal
from app.graph_mail import Attachment, Message
from app.graph import GraphClient
from app.graph_actions import GraphActions
from app.graph_state import ActionStore
from app.processing import ProcessingService, GraphProcessing
from app.processing_state import ProcessingStore, messages
from app.processing_decisions import DecisionStore
from app.process_queries import ProcessQueries, archive_boundary
from app.preview import PreviewManager
from app.security import Runtime
from app.settings import LdapSettings
from app.storage import StorageResult
from app.storage_state import StorageStore
from test_preview import CFG, DirectoryDouble
from test_graph import CONFIG, Credential
from test_processing import PathFiles
from preview_test_support import isolated_reader, remote_for, maximum_chunks, MAX_BYTES, XML
import httpx

if os.environ.get('AP06_ISOLATED_TEST')!='1' or os.environ.get('INTEGRATION_DB')=='1':
    raise RuntimeError('Only isolated test server with private SQLite allowed')


def fixture_runtime():
    temp=tempfile.TemporaryDirectory(prefix='ap06-browser-')
    root=Path(temp.name);engine=sa.create_engine('sqlite:///'+str(root/'fixture.sqlite'),connect_args={'check_same_thread':False})
    with patch('app.database.make_engine',return_value=engine):command.upgrade(Config('alembic.ini'),'head')
    bind=root/'bind';bind.write_text('bootstrap bind pass \n');bind.chmod(0o600)
    runtime=Runtime(engine,Fernet(Fernet.generate_key()),DirectoryDouble(),'https://ui:8443',str(bind))
    runtime.store.activate(LdapSettings(**CFG),None,'isolated-bootstrap',None)
    store=ProcessingStore(engine);storage=StorageStore(engine,destination_key='d'*64)
    original=Path('/test-input/original.pdf');size=original.stat().st_size
    if not 5<=size<=MAX_BYTES:raise RuntimeError('Existing test PDF must fit the original limit')
    checksum=hashlib.sha256()
    with original.open('rb') as source:
        if source.read(5)!=b'%PDF-':raise RuntimeError('Existing PDF input required')
        source.seek(0)
        while chunk:=source.read(65536):checksum.update(chunk)
    private_hash=checksum.hexdigest()
    maximum_hash=hashlib.sha256()
    for chunk in maximum_chunks():maximum_hash.update(chunk)
    folders={name:'folder-'+name for name in ('Failed','unzugeordnet','Mahnung','Nachfragen','Zahlungsavis','Success')}
    def seed(mid,specs,*,close=True,archive=False,failed=False):
        key=store.register('invoice@example.invalid',Message(mid,datetime(2026,12,1,tzinfo=timezone.utc),'inbox','notFlagged'),
            [Attachment(aid,name,length,'application/octet-stream',False,'file') for aid,name,length,sha,category in specs])
        owned=store.claim(key)
        for aid,name,length,sha,category in specs:
            row=next(row for row in store.get_attachments(key) if row['graph_id']==aid)
            store.content(key,row['attachment_key'],owned['owner'],0,byte_size=length,sha256=sha)
            store.finding(key,row['attachment_key'],owned['owner'],0,dict(status='failed' if failed else 'recognized' if category else 'unknown',category=category,
                reason='processing_classifier_unavailable' if failed else 'invoice_fields' if category else 'ambiguous_pdf',method='pdf_text',format='XML' if name.endswith('.xml') else 'PDF',original_sha256=sha,rule_version='ap03-4'))
            if category:
                request=store.begin_storage(key,row['attachment_key'],owned['owner'],0,'isolated-ui','d'*64)
                receipt=storage.claim(request);storage.begin_publication(request.key,receipt['owner']);storage.finish(request.key,receipt['owner'],'stored')
                store.stored(key,row['attachment_key'],owned['owner'],0,StorageResult(request.key,'stored',receipt['target']))
        if close:
            intent=store.prepare_close(key,owned['owner'],0,folders)
            store.finish_close(key,owned['owner'],0,parent_id=intent['destination_id'],flagged=True,intent_key=intent['intent_key'])
        else:store.release(key,owned['owner'],0)
        if archive:
            with engine.begin() as c:c.execute(messages.update().where(messages.c.message_key==key).values(created_at=archive_boundary(time.time())-1))
        return key
    active=seed('isolated-private',[('a1','Test-PDF.pdf',size,private_hash,None),('a2','Zweiter Anhang.pdf',size,private_hash,None),
        ('a3','Vorhandener Beleg.xml',len(XML),hashlib.sha256(XML).hexdigest(),'E-Rechnung')])
    archived=seed('isolated-archive',[('a1','Archiv-PDF.pdf',size,private_hash,None)],archive=True)
    maximum=seed('isolated-limit',[('a1','maximum.pdf',MAX_BYTES,maximum_hash.hexdigest(),None),
        ('a2','maximum.pdf',MAX_BYTES,maximum_hash.hexdigest(),None)],close=False)
    retrycase=seed('isolated-retry',[('a1','Technischer Fehler.pdf',size,private_hash,None)],failed=True)
    app.state.fixture=dict(temp=temp,store=store,storage=storage,active=active,archived=archived,maximum=maximum,retrycase=retrycase,
        original_sha256=private_hash,original_size=size,folders=folders,source_mode='normal')
    return runtime


app=create_app(fixture_runtime)
normal_lifespan=app.router.lifespan_context
class IsolatedPreview(PreviewManager):
    def snapshot(self,key,*,enabled=True):
        value=super().snapshot(key,enabled=enabled)
        value['test_mode']=app.state.fixture['source_mode']
        return value
@contextlib.asynccontextmanager
async def isolated_lifespan(application):
    async with normal_lifespan(application):
        application.state.preview=IsolatedPreview(application.state.runtime.engine,worker=isolated_reader,child_seconds=10,response_seconds=12)
        yield
    application.state.fixture['temp'].cleanup()
app.router.lifespan_context=isolated_lifespan


@app.get('/api/test/state')
def state():
    f=app.state.fixture
    return {name:f[name] for name in ('active','archived','maximum','retrycase','original_sha256','original_size')}


@app.get('/api/test/resources')
async def resources():
    manager=app.state.preview;root=manager.root
    free=0
    while free<2 and manager.slots.acquire(blocking=False):free+=1
    for _ in range(free):manager.slots.release()
    usage=os.statvfs(root)
    return dict(free_slots=free,directories=len(list(root.iterdir())),used_bytes=(usage.f_blocks-usage.f_bfree)*usage.f_frsize,
        capacity_bytes=usage.f_blocks*usage.f_frsize,raw_ready=len(list(root.glob('read-*/raw-ready'))))


@app.post('/api/test/advance')
async def advance():
    # Existing middleware requires current admin + Origin/CSRF even in this test server.
    # The bounded synthetic operator uses the real main-thread signal deadlines.
    f=app.state.fixture;store=f['store'];key=f['active']
    store.start_corrections(key)
    message=store.get_message(key);rows=store.get_attachments(key)
    remote=remote_for(message,rows)
    with httpx.Client(transport=httpx.MockTransport(remote),trust_env=False) as http:
        client=GraphClient(CONFIG,Credential(),http,sleep=lambda _:None)
        files=PathFiles();service=ProcessingService(store,GraphProcessing(client,GraphActions(client,ActionStore(store.engine))),f['storage'],files,'isolated-ui')
        for _ in range(8):
            with tempfile.TemporaryDirectory(prefix='advance-',dir=f['temp'].name) as directory:
                result=service.advance(key,directory)
            if result.status in {'done','waiting_correction','failed','operator_required'}:break
        else:raise RuntimeError('Bounded synthetic advance did not finish')
    return dict(status=result.status,published=len(files.published),detail=ProcessQueries(store.engine).detail(key))

@app.post('/api/test/retry-fail')
def retry_fail():
    f=app.state.fixture;store=f['store'];key=f['retrycase']
    revision=DecisionStore(store).consume_retry(key)
    if revision is not None:
        owned=store.claim(key);row=store.get_attachments(key)[0]
        store.content(key,row['attachment_key'],owned['owner'],revision,byte_size=row['byte_size'],sha256=row['raw_sha256'])
        store.failed(key,row['attachment_key'],owned['owner'],revision,'processing_classifier_unavailable')
        intent=store.prepare_close(key,owned['owner'],revision,f['folders'])
        store.finish_close(key,owned['owner'],revision,parent_id=intent['destination_id'],flagged=True,intent_key=intent['intent_key'])
    return ProcessQueries(store.engine).detail(key)


class SourceMode(BaseModel):
    mode: Literal['normal','missing','changed']


@app.post('/api/test/source-mode')
def source_mode(candidate:SourceMode):
    app.state.fixture['source_mode']=candidate.mode
    return {'mode':candidate.mode}
