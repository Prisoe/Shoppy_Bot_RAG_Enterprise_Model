"""
Policy enforcer middleware stub.
Actual enforcement happens inside the agent runner for full context.
This middleware can handle request-level org-wide blocks.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class PolicyEnforcerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Future: load org-level IP allowlists, rate limits, kill switches here
        return await call_next(request)
