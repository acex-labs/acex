from acex_client.acex.acex import Acex


def get_sdk(context):
    if not context:
        raise RuntimeError("No active context. Use 'acex context use' to select one.")
    url = context.get("url")
    if not url:
        raise RuntimeError("Active context saknar 'url'.")
    jwt = context.get("jwt")

    verify = context.get("verify_ssl", True)

    return Acex(baseurl=f"{url}/", verify=verify)
