import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from app.core.logging import request_id_ctx


class TracingMiddleware(BaseHTTPMiddleware):
    """
    Extracts or generates an X-Request-ID for every incoming request,
    stores it in request.state and the async ContextVar, and returns
    it in the response headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract from header or generate new UUID4
        incoming_id = request.headers.get("X-Request-ID")
        if incoming_id and len(incoming_id) <= 64:
            request_id = incoming_id
        else:
            request_id = str(uuid.uuid4())

        # Attach to request state for handlers to access
        request.state.request_id = request_id

        # Bind to ContextVar for structured logging
        token = request_id_ctx.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx.reset(token)
