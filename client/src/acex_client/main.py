
from acex.acex import Acex


a = Acex(baseurl = "http://127.0.0.1/")


missing_neds = a.neds.get_missing()

for missing_ned in missing_neds:
    a.neds.install(missing_ned)




