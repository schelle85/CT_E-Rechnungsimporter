"""Test-image-only Graph source for isolated browser/resource checks. Never in API image."""
import contextlib
import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
import httpx
from app.graph import GraphClient
from app.preview_worker import preview_child, MAX_BYTES
from app.graph_actions import FOLDERS
from test_graph import CONFIG, Credential
from test_graph_actions import ActionRemote
from test_graph_mail import message

PDF_PREFIX=b'%PDF-1.7\n'
PDF_END=b'\n%%EOF\n'
XML=b'<synthetic/>'


def maximum_chunks():
    yield PDF_PREFIX
    remaining=MAX_BYTES-len(PDF_PREFIX)-len(PDF_END)
    while remaining:
        count=min(65536,remaining);yield b'0'*count;remaining-=count
    yield PDF_END


class SourceStream(httpx.SyncByteStream):
    def __init__(self,row,changed=False):self.row,self.changed=row,changed
    def __iter__(self):
        name=json.loads(self.row['source'])[1]
        if name=='maximum.pdf':yield from maximum_chunks()
        elif name.endswith('.xml'):yield XML
        else:
            with Path('/test-input/original.pdf').open('rb') as source:
                first=True
                while chunk:=source.read(65536):
                    if first and self.changed:chunk=bytes([chunk[0]^1])+chunk[1:]
                    first=False;yield chunk


def remote_for(message_row,rows,mode="normal"):
    remote=ActionRemote();mid=message_row['graph_id']
    remote.folders={name:{'id':'folder-'+name,'displayName':name,'parentFolderId':'inbox','isHidden':False} for name in FOLDERS}
    remote.messages={mid:message(mid=mid,timestamp=message_row['received_at'],parent=message_row['current_parent'],flag='flagged')}
    def attachment(row):
        source=json.loads(row['source'])
        return {'id':source[0],'name':source[1],'size':source[2],'contentType':source[3],
            'isInline':source[4],'@odata.type':'#microsoft.graph.'+source[5]+'Attachment'}
    remote.attachments={mid:[attachment(row) for row in rows]}
    by_id={row['graph_id']:row for row in rows}
    def content(request):
        if request.url.path.endswith('/$value'):
            aid=request.url.path.split('/')[-2];row=by_id[aid]
            if mode=='missing':return httpx.Response(404)
            return httpx.Response(200,headers={'Content-Length':str(row['byte_size'])},stream=SourceStream(row,changed=mode=='changed'))
    remote.override=content
    return remote


def isolated_reader(connection,snapshot,directory,*_):
    if os.environ.get('AP06_ISOLATED_TEST')!='1':raise RuntimeError('Isolated test image marker required')
    remote=remote_for(snapshot['message'],snapshot['rows'],snapshot.get('test_mode','normal'))
    actual_temporary=tempfile.TemporaryFile
    @contextlib.contextmanager
    def held_temporary(*args,**kwargs):
        with actual_temporary(*args,**kwargs) as stream:
            yield stream
            if snapshot['filename']=='maximum.pdf':
                # Hold both actual Graph temp files plus both opaque output files
                # briefly, so the native tmpfs peak is observable without large IPC.
                ready=Path(directory)/'raw-ready';ready.write_text('ready');ready.chmod(0o600)
                root=Path(directory).parent;deadline=time.monotonic()+8
                while len(list(root.glob('read-*/raw-ready')))<2:
                    if time.monotonic()>deadline:raise RuntimeError('Isolated two-reader barrier timed out')
                    time.sleep(0.01)
                time.sleep(0.3)
    with httpx.Client(transport=httpx.MockTransport(remote),trust_env=False) as http:
        client=GraphClient(CONFIG,Credential(),http,sleep=lambda _:None)
        with patch('app.preview_worker.operator_client',return_value=contextlib.nullcontext(client)),patch('app.graph_mail.TemporaryFile',side_effect=held_temporary):
            preview_child(connection,snapshot,directory,'unused','unused')