"""The web test action owns one deadline before AD, DB and body preflight."""
import asyncio
import time
from starlette.responses import JSONResponse
from app.notification_model import OperationBudget

class NotificationBudgetBoundary:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if (scope["type"] != "http" or scope.get("method") != "POST"
                or scope.get("path","").rstrip("/") not in {"/api/notifications/test","/api/notifications/test/preview"}):
            await self.app(scope,receive,send);return
        budget=OperationBudget(clock=time.monotonic)
        scope.setdefault("state",{})["notification_budget"]=budget
        started=False
        async def forward(message):
            nonlocal started
            if message["type"] == "http.response.start":started=True
            await send(message)
        try:
            async with asyncio.timeout(budget.remaining()):
                await self.app(scope,receive,forward)
        except TimeoutError:
            if started:raise
            await JSONResponse(status_code=504,content=dict(detail="Zeitbudget abgelaufen. Ursprüngliche Anforderung über Status abgleichen.",
                code="notification_deadline",persisted=False),headers={"Cache-Control":"no-store"})(scope,receive,send)
