import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def debug_error_middleware(get_response):
    """logs debug info for all 4xx api responses"""

    def middleware(request):
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

        if request.body:
            data["body"] = request.body.decode(errors="replace")

        if settings.DEBUG_LOG_API_KEY:
            api_keys = {}
            for key in ("x-api-key", "x-apikey", "X-API-KEY"):
                val = request.headers.get(key)
                if val:
                    api_keys[f"header:{key}"] = val
                val = request.GET.get(key)
                if val:
                    api_keys[f"query:{key}"] = val
            if api_keys:
                data["api_keys"] = api_keys

        logger.debug("api error", extra={"request_context": data})

        return response

    return middleware
