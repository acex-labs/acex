
from acex_client.acex.acex import Acex

from acex_client.acex.resources.credential import Credentials

a = Acex(
    baseurl = "http://127.0.0.1:8080/",
    verify=False
)
# a = Acex(baseurl = "https://api.auto.ngninfra.net/", verify=False)

