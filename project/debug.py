import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def debug_error_middleware(get_response):
    """logs debug info for all 4xx api responses"""

    def middleware(request):
        # read body before DRF consumes the stream
        try:
            raw = request.body.decode(errors="replace") if request.body else None
        except Exception:
            raw = None

        body = None
        if raw:
            try:
                body = json.loads(raw)
            except json.JSONDecodeError, ValueError:
                body = raw

        response = get_response(request)

        if response.status_code < 400 or response.status_code >= 500:
            return response

        if not request.path.startswith("/api/"):
            return response

        data = {
            "status": response.status_code,
            "method": request.method,
            "path": request.get_full_path(),
        }

        if hasattr(response, "data"):
            data["response"] = response.data

        if body:
            data["body"] = body

        if settings.DEBUG_LOG_API_KEY:
            api_keys = {}
            for key in ("x-api-key", "x-apikey"):
                # headers are case-insensitive
                val = request.headers.get(key)
                if val:
                    api_keys[f"header:{key}"] = val
                # query params are case-sensitive, check both casings
                for qkey in (key, key.upper()):
                    val = request.GET.get(qkey)
                    if val:
                        api_keys[f"query:{qkey}"] = val
            if api_keys:
                data["api_keys"] = api_keys

        logger.debug("api error", extra={"request_context": data})

        return response

    return middleware
