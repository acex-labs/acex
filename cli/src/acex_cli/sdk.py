from acex_client.acex.acex import Acex
import requests
from requests.exceptions import ConnectionError, SSLError


def _innermost_exception_message(exc: Exception) -> str:
    cause = exc
    while getattr(cause, "__cause__", None):
        cause = cause.__cause__
    return str(cause)


def get_sdk(context):
    if not context:
        raise RuntimeError("No active context. Use 'acex context use' to select one.")
    url = context.get("url")
    if not url:
        raise RuntimeError("Active context saknar 'url'.")
    jwt = context.get("jwt")

    verify = context.get("verify_ssl", True)
    client = Acex(baseurl=f"{url}/", verify=verify)
    return client
