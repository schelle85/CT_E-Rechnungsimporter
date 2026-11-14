"""Real spawned reader lifetimes and authenticated original HTTP route; synthetic bytes only."""
import asyncio
import hashlib
import json
import multiprocessing
from pathlib import Path
import time
import unittest
import sqlalchemy as sa
import test_process_api as fixture
from app.graph_mail import Attachment, Message
from datetime import datetime, timezone
from app.preview import PreviewManager
from app.processing_state import attachments, messages

PDF=b'%PDF-1.7\nsynthetic preview\n%%EOF\n'
TEXT=b'synthetic plain text'


def good_worker(connection,snapshot,directory,*_):
    data=TEXT if snapshot['filename'].endswith('.txt') else PDF
    (Path(directory)/'original').write_bytes(data)
    (Path(directory)/'original').chmod(0o600)
    connection.send_bytes(json.dumps(dict(ok=True,size=len(data),sha256=hashlib.sha256(data).hexdigest(),pdf=data==PDF)).encode())
    connection.close()


def slow_worker(connection,snapshot,directory,*_):
    time.sleep(30)


def changed_worker(connection,snapshot,directory,*_):
    (Path(directory)/'original').write_bytes(b'x'*len(PDF))
    (Path(directory)/'original').chmod(0o600)
    connection.send_bytes(json.dumps(dict(ok=True,size=len(PDF),sha256=snapshot['selected']['raw_sha256'],pdf=True)).encode())
    connection.close()


class OriginalTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixture.ProcessApiTests.asyncSetUp(self)
        self.preview_root=Path(self.temp.name)/'preview';self.preview_root.mkdir(mode=0o700)
        self.manager=PreviewManager(self.engine,root=self.preview_root,worker=good_worker,child_seconds=3,response_seconds=6)
        self.app.state.preview=self.manager
        self.counter=0

    asyncTearDown=fixture.ProcessApiTests.asyncTearDown
    challenge=fixture.ProcessApiTests.challenge
    headers=fixture.ProcessApiTests.headers
    login=fixture.ProcessApiTests.login

    def source(self,filename='synthetic.pdf'):
        self.counter+=1
        data=TEXT if filename.endswith('.txt') else PDF
        key=self.store.register('invoice@example.invalid',Message('preview'+str(self.counter),datetime(2026,12,1,tzinfo=timezone.utc),'inbox','notFlagged'),
            [Attachment('a1',filename,len(data),'application/octet-stream',False,'file')])
        owned=self.store.claim(key);row=self.store.get_attachments(key)[0]
        self.store.content(key,row['attachment_key'],owned['owner'],0,byte_size=len(data),sha256=hashlib.sha256(data).hexdigest())
        self.store.finding(key,row['attachment_key'],owned['owner'],0,dict(status='unknown',category=None,reason='ambiguous_pdf',
            method='pdf_text',format='PDF' if data==PDF else 'TXT',original_sha256=hashlib.sha256(data).hexdigest(),rule_version='ap03-4'))
        self.store.release(key,owned['owner'],0)
        return key,row['attachment_key']

    def clean(self):
        self.assertEqual(list(self.preview_root.iterdir()),[])
        self.assertFalse(multiprocessing.active_children())
        self.assertTrue(self.manager.slots.acquire(blocking=False))
        self.assertTrue(self.manager.slots.acquire(blocking=False))
        self.assertFalse(self.manager.slots.acquire(blocking=False))
        self.manager.slots.release();self.manager.slots.release()

    async def test_reader_get_head_single_range_if_range_and_download_are_integrity_bound(self):
        key,aid=self.source('../name\r\n.pdf')
        path='/api/attachments/'+aid+'/original'
        self.assertEqual((await self.client.get(path)).status_code,401)
        await self.login('reader')
        before=self.store.get_message(key),self.store.get_attachments(key)
        response=await self.client.get(path)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.content,PDF)
        self.assertTrue(response.headers['content-disposition'].startswith('inline;'))
        self.assertNotIn('\r',response.headers['content-disposition'])
        self.assertEqual(response.headers['content-type'],'application/pdf')
        head=await self.client.head(path)
        self.assertEqual(head.content,b'')
        self.assertEqual(int(head.headers['content-length']),len(PDF))
        part=await self.client.get(path,headers={'Range':'bytes=2-8'})
        self.assertEqual((part.status_code,part.content),(206,PDF[2:9]))
        self.assertEqual(part.headers['content-range'],'bytes 2-8/'+str(len(PDF)))
        changed=await self.client.get(path,headers={'Range':'bytes=2-8','If-Range':'"different"'})
        self.assertEqual((changed.status_code,changed.content),(200,PDF))
        download=await self.client.get(path+'?download=true')
        self.assertTrue(download.headers['content-disposition'].startswith('attachment;'))
        self.assertEqual(download.headers['cache-control'],'no-store')
        self.assertEqual(download.headers['x-content-type-options'],'nosniff')
        self.assertEqual((self.store.get_message(key),self.store.get_attachments(key)),before)
        self.clean()

    async def test_invalid_multi_ranges_non_pdf_unknown_key_and_bad_hash_cleanup(self):
        _,aid=self.source();await self.login('admin')
        path='/api/attachments/'+aid+'/original'
        for headers in ({'Range':'bytes=0-1,3-4'},{'Range':'nonsense'},[('Range','bytes=0-1'),('Range','bytes=3-4')]):
            result=await self.client.get(path,headers=headers)
            self.assertEqual(result.status_code,416,result.text)
            self.assertEqual(result.headers['cache-control'],'no-store')
            self.assertEqual(result.headers['content-range'],'bytes */'+str(len(PDF)))
        _,plain=self.source('plain.txt')
        result=await self.client.get('/api/attachments/'+plain+'/original')
        self.assertEqual(result.content,TEXT)
        self.assertTrue(result.headers['content-disposition'].startswith('attachment;'))
        self.assertEqual(result.headers['content-type'],'application/octet-stream')
        self.assertEqual((await self.client.get('/api/attachments/'+'0'*64+'/original')).status_code,404)
        self.manager.worker=changed_worker
        self.assertEqual((await self.client.get(path)).status_code,409)
        self.clean()

    async def test_child_deadline_and_disabled_preview_leave_no_resources(self):
        _,aid=self.source();await self.login('reader')
        self.manager.worker=slow_worker;self.manager.child_seconds=0.2
        started=time.monotonic()
        self.assertEqual((await self.client.get('/api/attachments/'+aid+'/original')).status_code,504)
        self.assertLess(time.monotonic()-started,3)
        self.clean()
        from app.processing_state import controls
        with self.engine.begin() as c:c.execute(controls.update().values(preview_enabled=0))
        self.assertEqual((await self.client.get('/api/attachments/'+aid+'/original')).status_code,503)
        self.clean()

    async def direct(self,aid,send,disconnected=None):
        first=True
        async def receive():
            nonlocal first
            if first:first=False;return {'type':'http.request','body':b'','more_body':False}
            if disconnected is None:await asyncio.Event().wait()
            else:await disconnected.wait()
            return {'type':'http.disconnect'}
        scope={'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'method':'GET','path':'/original',
               'headers':[],'extensions':{'http.response.pathsend':{}}}
        await self.manager.response(aid)(scope,receive,send)

    async def test_two_slots_remain_held_during_transfer_third_is_bounded_and_abort_cleans(self):
        _,aid=self.source()
        ready=[asyncio.Event(),asyncio.Event()]
        async def send(index,message):
            self.assertNotEqual(message['type'],'http.response.pathsend')
            if message['type']=='http.response.body':ready[index].set();await asyncio.Event().wait()
        tasks=[asyncio.create_task(self.direct(aid,lambda message,i=i:send(i,message))) for i in range(2)]
        try:
            await asyncio.wait_for(asyncio.gather(*[event.wait() for event in ready]),5)
            responses=[]
            async def collect(message):responses.append(message)
            await self.direct(aid,collect)
            self.assertEqual(responses[0]['status'],503)
            self.assertEqual(len(list(self.preview_root.iterdir())),2)
        finally:
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
        self.clean()

    async def test_disconnect_during_child_and_total_response_deadline_cleanup(self):
        _,aid=self.source();self.manager.worker=slow_worker
        disconnected=asyncio.Event()
        async def send(_):pass
        task=asyncio.create_task(self.direct(aid,send,disconnected))
        for _ in range(100):
            if list(self.preview_root.iterdir()):break
            await asyncio.sleep(0.01)
        disconnected.set();await asyncio.wait_for(task,3)
        self.clean()
        self.manager.worker=good_worker;self.manager.response_seconds=1.5
        entered=asyncio.Event()
        async def stalled(message):
            if message['type']=='http.response.body':entered.set();await asyncio.Event().wait()
        task=asyncio.create_task(self.direct(aid,stalled))
        await asyncio.wait_for(entered.wait(),1.4)
        result=await asyncio.wait_for(asyncio.gather(task,return_exceptions=True),3)
        self.assertIsInstance(result[0],BaseException)
        self.clean()

    async def test_revision_change_during_fetch_rejects_output(self):
        key,aid=self.source();await self.login('reader')
        # Recheck is independent from child metadata and cannot trust the old revision.
        original=self.manager.verify
        def changed(path,selected):
            result=original(path,selected)
            with self.engine.begin() as c:c.execute(messages.update().where(messages.c.message_key==key).values(revision=1))
            return result
        self.manager.verify=changed
        self.assertEqual((await self.client.get('/api/attachments/'+aid+'/original')).status_code,409)
        self.clean()
    async def test_real_reader_uses_only_get_and_both_files_are_in_private_directory(self):
        import contextlib
        import os
        import tempfile
        from unittest.mock import patch
        import httpx
        from app.graph import GraphClient, GraphError
        from app.preview_worker import read_original, ReadOnlyGraph
        from test_graph import CONFIG, Credential
        from test_graph_actions import ActionRemote
        from test_graph_mail import attachment, message
        key,aid=self.source()
        snapshot=self.manager.snapshot(aid)
        remote=ActionRemote()
        remote.messages={'preview1':message(mid='preview1',timestamp='2026-12-01T00:00:00+00:00')}
        remote.attachments={'preview1':[attachment('a1',size=len(PDF),name='synthetic.pdf')]}
        remote.raw=PDF
        original_temp=tempfile.tempdir
        before=self.store.get_message(key),self.store.get_attachments(key)
        with tempfile.TemporaryDirectory(dir=self.preview_root) as directory:
            actual_temporary=tempfile.TemporaryFile
            raw_locations=[]
            def private_temporary(*args,**kwargs):
                result=actual_temporary(*args,**kwargs)
                raw_locations.append(os.readlink('/proc/self/fd/'+str(result.fileno())))
                return result
            try:
                with httpx.Client(transport=httpx.MockTransport(remote),trust_env=False) as http:
                    client=GraphClient(CONFIG,Credential(),http,sleep=lambda _:None)
                    with patch('app.preview_worker.operator_client',return_value=contextlib.nullcontext(client)),patch('app.graph_mail.TemporaryFile',side_effect=private_temporary):
                        result=read_original(snapshot,directory,'unused','unused')
                    self.assertTrue(result['pdf'])
                    self.assertEqual((Path(directory)/'original').read_bytes(),PDF)
                    for method in ('POST','PATCH'):
                        with self.assertRaises(GraphError):ReadOnlyGraph(client)._json(method,client.root)
                self.assertTrue(raw_locations)
                self.assertTrue(all(path.startswith(directory+'/') for path in raw_locations))
            finally:tempfile.tempdir=original_temp
        self.assertTrue(remote.calls)
        self.assertTrue(all(call.method=='GET' for call in remote.calls))
        self.assertFalse(remote.writes)
        self.assertEqual((self.store.get_message(key),self.store.get_attachments(key)),before)
        self.clean()
