"""Existing AD/CSRF boundary as direct ASGI: never buffer original response bodies."""
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from app.errors import AccessError
from app.security import COOKIE


class SecurityBoundary:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':
            await self.app(scope,receive,send)
            return
        request=Request(scope,receive=receive)
        runtime=request.app.state.runtime
        path=request.url.path
        public={'/api/health/live','/api/health/ready','/api/auth/session','/api/auth/login'}
        started=False
        async def forward(message):
            nonlocal started
            if message['type']=='http.response.start':
                started=True
                message=dict(message,headers=[(k,v) for k,v in message.get('headers',[]) if k.lower()!=b'cache-control']+[(b'cache-control',b'no-store')])
            # Await actual downstream backpressure, including the final body chunk.
            await send(message)
        try:
            if path.startswith('/api/') and path not in public:
                row,principal=await run_in_threadpool(runtime.require,request,path!='/api/auth/logout')
                request.state.principal=principal
                request.state.session=row
                if request.method not in ('GET','HEAD','OPTIONS'):
                    runtime.csrf(request,row)
                    if path!='/api/auth/logout' and principal.role!='admin':
                        raise AccessError(403,'Verwaltungsrecht erforderlich.')
            await self.app(scope,receive,forward)
        except AccessError as error:
            if started:raise
            response=JSONResponse({'detail':error.detail},status_code=error.status)
            if error.status==401 and path!='/api/auth/login':
                response.delete_cookie(COOKIE,secure=True,httponly=True,samesite='strict',path='/')
            await response(scope,receive,forward)
        except SQLAlchemyError:
            if started:raise
            await JSONResponse({'detail':'Dienst vorübergehend nicht bereit.'},status_code=503)(scope,receive,forward)