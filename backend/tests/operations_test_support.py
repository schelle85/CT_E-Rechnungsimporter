from copy import deepcopy
from app.operations_status import JOBS

SOURCE="a"*40
DEPLOYMENT="11111111-1111-1111-1111-111111111111"
INSTANCE="22222222-2222-2222-2222-222222222222"
BOOT="33333333-3333-3333-3333-333333333333"
NOW=1794835000


def raw(now=NOW,instance=INSTANCE):
    return dict(schema_version=1,source_commit=SOURCE,deployment_id=DEPLOYMENT,instance_id=instance,boot_id=BOOT,
        generated_at=now,timezone="Europe/Berlin",draining=False,processing_running=False,
        startup=dict(configured=True,active=True,ready=True,database_ready=True,nginx_ready=True,last_result="ok",last_run_at=now-60),
        mounts=dict(importer=True,tls_source=True),jobs={name:dict(configured=True,active=True,running=False,blocked=False,
            last_result="ok",last_run_at=now-60,next_run_at=now+60) for name in JOBS})


def changed(value,path,item):
    value=deepcopy(value);target=value
    for key in path[:-1]:target=target[key]
    target[path[-1]]=item
    return value
