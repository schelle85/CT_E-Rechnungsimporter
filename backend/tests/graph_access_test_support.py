"""Explicit test-only admission for synthetic transports, never shipped in images."""
from contextlib import contextmanager
from unittest.mock import patch
from app import graph_access_runtime as runtime
from app.graph_access import AccessBinding

BOUND=AccessBinding("a"*40,"22222222-2222-2222-2222-222222222222",
    "33333333-3333-3333-3333-333333333333","b"*64)


class SyntheticAccess:
    def check(self,*_,**__):pass


def transport_access():
    return dict(access=SyntheticAccess(),access_material=(b"synthetic-transport","c"*64))


@contextmanager
def admitted_transport(*_,**__):
    """Only tests replacing HTTP/SDK may use this explicit scoped seam."""
    with patch.object(runtime,"binding",return_value=BOUND):
        if runtime.current() is not None:yield runtime.current().permit
        else:
            with runtime._use(BOUND,SyntheticAccess()) as permit:yield permit
