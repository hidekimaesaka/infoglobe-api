from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock
from time import monotonic

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        max_requests: int = 40,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests_by_ip: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    async def dispatch(self, request: Request, call_next: Callable):
        client_ip = self._get_client_ip(request)
        current_time = monotonic()

        with self._lock:
            timestamps = self._requests_by_ip[client_ip]
            self._prune_expired_requests(timestamps, current_time)

            if len(timestamps) >= self.max_requests:
                retry_after = self._retry_after_seconds(timestamps, current_time)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded."},
                    headers={"Retry-After": str(retry_after)},
                )

            timestamps.append(current_time)

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            first_ip = forwarded_for.split(",")[0].strip()
            if first_ip:
                return first_ip

        if request.client and request.client.host:
            return request.client.host

        return "unknown"

    def _prune_expired_requests(self, timestamps: deque[float], current_time: float) -> None:
        while timestamps and current_time - timestamps[0] >= self.window_seconds:
            timestamps.popleft()

    def _retry_after_seconds(self, timestamps: deque[float], current_time: float) -> int:
        if not timestamps:
            return self.window_seconds
        elapsed = current_time - timestamps[0]
        remaining = self.window_seconds - elapsed
        return max(1, int(remaining))
