from acex_client.acex.acex import Acex
import requests


def get_sdk(context):
    if not context:
        raise RuntimeError("No active context. Use 'acex context use' to select one.")
    url = context.get("url")
    if not url:
        raise RuntimeError("Active context saknar 'url'.")
    jwt = context.get("jwt")

    verify = context.get("verify_ssl", True)

    client = Acex(baseurl=f"{url}/", verify=verify)

    print(client.api_url)
    try:
        requests.head(client.api_url)
    except requests.ConnectionError as e:
        print(f"\033[91mCould not connect to API\033[0m\r\n\r\n{e}")
        exit()
    return client
