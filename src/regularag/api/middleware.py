from starlette.responses import JSONResponse

from regularag.core.tracing import request_trace, stage


class RequestTraceMiddleware:
    def __init__(self, app, enabled=True):
        self.app = app
        self.enabled = enabled

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        is_ask = scope.get("path") == "/api/v1/ask" and scope.get("method") == "POST"
        with request_trace(enabled=self.enabled and is_ask) as trace:
            scope["regularag.request_id"] = trace.request_id
            status = 500
            response_started = False

            async def traced_send(message):
                nonlocal status, response_started
                if message["type"] == "http.response.start":
                    response_started = True
                    status = message["status"]
                    headers = [
                        (k, v)
                        for k, v in message.get("headers", [])
                        if k.lower() != b"x-request-id"
                    ]
                    message = {
                        **message,
                        "headers": headers + [(b"x-request-id", trace.request_id.encode("ascii"))],
                    }
                await send(message)

            try:
                with stage("http.request") as span:
                    span.fields(route="/api/v1/ask", method="POST")
                    try:
                        await self.app(scope, receive, traced_send)
                    except Exception as error:
                        span.status = "failed"
                        span.error_type = type(error).__name__
                        trace.result = {
                            "status": "error",
                            "http_status": 500,
                            "error_type": type(error).__name__,
                        }
                        if response_started:
                            raise
                        # Keep unexpected exceptions observable without exposing their messages.
                        await JSONResponse(
                            {"detail": "Không thể xử lý yêu cầu.", "request_id": trace.request_id},
                            status_code=500,
                        )(scope, receive, traced_send)
                    finally:
                        span.fields(http_status=status)
            finally:
                trace.emit()
