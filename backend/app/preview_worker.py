"""Non-privileged spawned reader; no journal mutations and only GET Graph methods."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from app.graph import GraphError, operator_client
from app.graph_mail import Mailbox
from app.processing_graph import JournalMailbox
from app.storage_plan import digest

MAX_BYTES=26214400


class ReadOnlyGraph:
    def __init__(self, client):
        self._client=client
        self.config,self.root,self.clock=client.config,client.root,client.clock

    def _checked_url(self, *args, **kwargs):
        return self._client._checked_url(*args,**kwargs)

    def _json(self, method, *args, **kwargs):
        if method!='GET':raise GraphError('preview_write_forbidden')
        return self._client._json(method,*args,**kwargs)

    def _response(self, method, *args, **kwargs):
        if method!='GET':raise GraphError('preview_write_forbidden')
        return self._client._response(method,*args,**kwargs)


def read_original(snapshot, directory, config, credential):
    message=snapshot['message'];selected=snapshot['selected']
    tempfile.tempdir=directory  # Also controls graph_mail's existing TemporaryFile.
    with operator_client(config,credential) as raw:
        client=ReadOnlyGraph(raw)
        observed=Mailbox(client).message(message['graph_id'])
        allowed={message['current_parent']}
        if message['close_key'] and message['close_payload']:
            intent=json.loads(message['close_payload'])
            if intent.get('revision')!=message['revision'] or digest([message['message_key'],message['revision'],intent])!=message['close_key']:
                raise GraphError('preview_source_changed')
            allowed.add(intent['destination_id'])
        if observed.parent_id not in allowed or observed.received_at.isoformat()!=message['received_at']:
            raise GraphError('preview_source_changed')
        receipt=dict(message,current_parent=observed.parent_id)
        reader=JournalMailbox(client,receipt,snapshot['rows'])
        checksum,size,magic=hashlib.sha256(),0,b''
        path=Path(directory)/'original'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as output,reader.attachment_content(message['graph_id'],selected['graph_id']) as stream:
            while chunk:=stream.read(65536):
                size+=len(chunk)
                if size>MAX_BYTES:raise GraphError('preview_size_limit')
                if not magic:magic=chunk[:5]
                checksum.update(chunk);output.write(chunk)
            output.flush()
        if size!=selected['byte_size'] or checksum.hexdigest()!=selected['raw_sha256']:
            raise GraphError('preview_content_changed')
        # Revalidate selected source and full known manifest after the download as well.
        reader.attachments(message['graph_id'])
        finding=json.loads(selected['effective_finding'] or selected['original_finding'] or '{}')
        return {'ok':True,'size':size,'sha256':checksum.hexdigest(),'pdf':magic==b'%PDF-' and finding.get('format')=='PDF'}


def preview_child(connection, snapshot, directory, config, credential):
    try:
        try:result=read_original(snapshot,directory,config,credential)
        except GraphError as error:result={'ok':False,'code':error.code}
        except BaseException:result={'ok':False,'code':'preview_unavailable'}
        payload=json.dumps(result,separators=(',',':')).encode()
        if len(payload)>1024:payload=b'{"ok":false,"code":"preview_unavailable"}'
        connection.send_bytes(payload)
    finally:
        connection.close()