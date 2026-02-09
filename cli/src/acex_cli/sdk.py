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
    try:
        requests.head(client.api_url, verify=verify)
    except SSLError as e:
        reason = _innermost_exception_message(e)
        print(
            "\033[91mCould not connect to API due to untrusted certificate!\033[0m\r\n\r\n"
            f"Reason: {reason}"
        )
        exit()
    except ConnectionError as e:
        reason = _innermost_exception_message(e)
        print(
            "\033[91mCould not connect to API!\033[0m\r\n\r\n"
            f"Reason: {reason}"
        )
        exit()
    return client
