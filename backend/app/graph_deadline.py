"""Linux operator-process deadlines, including blocking reads and authentication."""
from contextlib import contextmanager
import multiprocessing
import signal
import threading
import time

from app.graph import GraphError


class _Expired(BaseException):
    # Auth/HTTP libraries must not turn this into an internal retry.
    pass


@contextmanager
def request_deadline(seconds, *, uncertain=False):
    if (not hasattr(signal, "setitimer") or threading.current_thread() is not threading.main_thread()
            or signal.getitimer(signal.ITIMER_REAL)[0]):
        raise GraphError("graph_deadline_unavailable")
    previous = signal.getsignal(signal.SIGALRM)
    def expired(*_):
        raise _Expired()
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    except _Expired:
        raise GraphError("graph_request_deadline", uncertain=uncertain) from None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _child(connection, operation, arguments):
    try:
        result = operation(*arguments)
    except GraphError as error:
        result = {"ok": False, "code": error.code, "status": error.status, "uncertain": error.uncertain}
    except BaseException:
        result = {"ok": False, "code": "graph_runtime_unavailable"}
    try:
        connection.send(result)
    finally:
        connection.close()


def bounded_operation(operation, arguments=(), *, seconds=180, uncertain=False):
    """Parent has no credential. Kill a stuck child; never restart/replay its work."""
    context = multiprocessing.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=_child, args=(send, operation, arguments))
    started = time.monotonic()
    try:
        process.start()
        send.close()
        if receive.poll(max(0, seconds - (time.monotonic() - started))):
            try:
                return receive.recv()
            except EOFError:
                return {"ok": False, "code": "graph_runtime_unavailable"}
        return {"ok": False, "code": "graph_operation_deadline", "uncertain": uncertain}
    finally:
        receive.close()
        send.close()
        if process.pid is not None:
            process.join(0)
            if process.is_alive():
                process.terminate()
                process.join(1)
            if process.is_alive():
                process.kill()
                process.join(1)
            process.close()
