"""Two bounded original responses, owning child, private files and slot until ASGI end."""
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import threading
import time
import anyio
import sqlalchemy as sa
from starlette.responses import Response, FileResponse, JSONResponse
from app.errors import AccessError
from app.process_queries import ProcessQueries, key_value
from app.processing_state import attachments, controls, messages
from app.preview_worker import MAX_BYTES, preview_child
from app.storage_plan import digest


class PreviewManager:
    def __init__(self, engine, *, root='/preview-tmpfs', worker=preview_child, child_seconds=180, response_seconds=300):
        self.engine,self.root,self.worker=engine,Path(root),worker
        self.child_seconds,self.response_seconds=child_seconds,response_seconds
        self.slots=threading.BoundedSemaphore(2)

    def snapshot(self, key, *, enabled=True):
        key_value(key)
        with ProcessQueries(self.engine).snapshot() as c:
            if enabled and not c.execute(sa.select(controls.c.preview_enabled).where(controls.c.singleton==1)).scalar_one_or_none():
                raise AccessError(503,'Originalvorschau ist derzeit deaktiviert.')
            selected=c.execute(sa.select(attachments).where(attachments.c.attachment_key==key)).mappings().first()
            if selected is None:raise AccessError(404,'Anhang nicht vorhanden.')
            selected=dict(selected)
            message=dict(c.execute(sa.select(messages).where(messages.c.message_key==selected['message_key'])).mappings().one())
            source=json.loads(selected['source'])
            if (source[5]!='file' or not re.fullmatch(r'[0-9a-f]{64}',selected['raw_sha256'] or '')
                    or type(selected['byte_size']) is not int or not 0<=selected['byte_size']<=MAX_BYTES):
                raise AccessError(409,'Für diesen Anhang liegt kein überprüfbares Original vor.')
            rows=[dict(row) for row in c.execute(sa.select(attachments).where(attachments.c.message_key==message['message_key'])).mappings()]
            bound=[{name:message[name] for name in ('message_key','revision','received_at','source_parent','current_parent','manifest_key','close_key','close_payload')},
                {name:selected[name] for name in ('attachment_key','source','raw_sha256','byte_size','finding_revision')}]
            return dict(message=message,rows=rows,selected=selected,fingerprint=digest(bound),filename=source[1])

    def directory(self):
        info=self.root.lstat()
        if not self.root.is_absolute() or not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o077:
            raise AccessError(503,'Originalvorschau vorübergehend nicht bereit.')
        return Path(tempfile.mkdtemp(prefix='read-',dir=self.root))

    @staticmethod
    def reap(process):
        if process is None:return
        if process.pid is not None:
            process.join(0)
            if process.is_alive():process.terminate();process.join(1)
            if process.is_alive():process.kill();process.join(1)
            if process.is_alive():raise RuntimeError('preview_child_cleanup_failed')
            process.close()

    @staticmethod
    def verify(path, selected):
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as stream:
            info=os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.geteuid() or info.st_mode&0o077 or info.st_size!=selected['byte_size'] or info.st_size>MAX_BYTES:
                raise AccessError(409,'Original konnte nicht vollständig überprüft werden.')
            checksum=hashlib.sha256()
            while chunk:=stream.read(65536):checksum.update(chunk)
            if checksum.hexdigest()!=selected['raw_sha256']:
                raise AccessError(409,'Original wurde zwischenzeitlich geändert.')
            return info

    def response(self,key,*,download=False):
        return ManagedOriginal(self,key,download)


class ManagedOriginal(Response):
    def __init__(self,manager,key,download):
        super().__init__(content=b'')
        self.manager,self.key,self.download=manager,key,download

    async def __call__(self,scope,receive,send):
        manager=self.manager
        if not manager.slots.acquire(blocking=False):
            await JSONResponse({'detail':'Beide Vorschauplätze sind belegt. Bitte kurz warten.'},status_code=503,
                headers={'Cache-Control':'no-store','Retry-After':'2','X-Content-Type-Options':'nosniff'})(scope,receive,send)
            return
        directory=process=receiver=sender=None
        started=False
        async def tracked(message):
            nonlocal started
            if message['type']=='http.response.start':
                started=True
                message=dict(message,headers=[(k,v) for k,v in message.get('headers',[]) if k.lower() not in {b'cache-control',b'x-content-type-options'}]+[
                    (b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff')])
            await send(message)
        try:
            async with anyio.create_task_group() as group:
                async def disconnect():
                    while True:
                        if (await receive())['type']=='http.disconnect':
                            group.cancel_scope.cancel();return
                group.start_soon(disconnect)
                try:
                    with anyio.fail_after(manager.response_seconds):
                        snapshot=await anyio.to_thread.run_sync(manager.snapshot,self.key)
                        directory=manager.directory()
                        context=multiprocessing.get_context('spawn')
                        receiver,sender=context.Pipe(duplex=False)
                        process=context.Process(target=manager.worker,args=(sender,snapshot,str(directory),
                            '/run/importer/graph.json','/run/secrets/graph_credential'),daemon=True)
                        process.start();sender.close()
                        deadline=time.monotonic()+manager.child_seconds
                        while not receiver.poll():
                            if time.monotonic()>=deadline:raise AccessError(504,'Originalabruf hat das Zeitlimit erreicht.')
                            if not process.is_alive():raise AccessError(503,'Originalquelle ist vorübergehend nicht verfügbar.')
                            await anyio.sleep(0.05)
                        result=json.loads(receiver.recv_bytes(4096))
                        await anyio.to_thread.run_sync(manager.reap,process);process=None
                        if not isinstance(result,dict) or result.get('ok') is not True:
                            raise AccessError(409,'Original ist nicht verfügbar oder wurde geändert.')
                        selected=snapshot['selected']
                        if result.get('size')!=selected['byte_size'] or result.get('sha256')!=selected['raw_sha256']:
                            raise AccessError(409,'Original konnte nicht vollständig überprüft werden.')
                        path=directory/'original'
                        details=await anyio.to_thread.run_sync(manager.verify,path,selected)
                        current=await anyio.to_thread.run_sync(lambda:manager.snapshot(self.key,enabled=False))
                        if current['fingerprint']!=snapshot['fingerprint']:
                            raise AccessError(409,'Vorgang wurde geändert. Bitte neu laden.')
                        ranges=[v for k,v in scope.get('headers',[]) if k.lower()==b'range']
                        value=ranges[0] if ranges else b''
                        if len(ranges)>1 or value and (len(value)>128 or not re.fullmatch(rb'bytes=\d*-\d*',value) or value==b'bytes=-'):
                            raise AccessError(416,'Nur ein gültiger einzelner Dateibereich ist erlaubt.')
                        name=re.sub(r'[\x00-\x1f\x7f/\\]','_',snapshot['filename'])[:180].strip(' .') or 'Original'
                        pdf=result.get('pdf') is True
                        response=FileResponse(path,stat_result=details,filename=name,
                            media_type='application/pdf' if pdf else 'application/octet-stream',
                            content_disposition_type='attachment' if self.download or not pdf else 'inline',
                            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','ETag':'"'+selected['raw_sha256']+'"'})
                        # No deferred pathsend: the file belongs to this response's lifetime.
                        inner=dict(scope,extensions={k:v for k,v in scope.get('extensions',{}).items() if k!='http.response.pathsend'})
                        if scope['method']=='HEAD':inner['headers']=[(k,v) for k,v in scope['headers'] if k.lower() not in {b'range',b'if-range'}]
                        await response(inner,receive,tracked)
                except AccessError as error:
                    if started:raise
                    extra={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
                    if error.status==416 and 'snapshot' in locals():extra['Content-Range']='bytes */'+str(snapshot['selected']['byte_size'])
                    await JSONResponse({'detail':error.detail},status_code=error.status,headers=extra)(scope,receive,tracked)
                except (OSError,ValueError,EOFError):
                    if started:raise
                    await JSONResponse({'detail':'Originalvorschau vorübergehend nicht bereit.'},status_code=503,
                        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})(scope,receive,tracked)
                except TimeoutError:
                    if started:raise
                    await JSONResponse({'detail':'Originalvorschau hat das Zeitlimit erreicht.'},status_code=504,
                        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})(scope,receive,tracked)
                finally:group.cancel_scope.cancel()
        finally:
            with anyio.CancelScope(shield=True):
                await anyio.to_thread.run_sync(manager.reap,process)
                if receiver is not None:receiver.close()
                if sender is not None:sender.close()
                if directory is not None:shutil.rmtree(directory)
                manager.slots.release()