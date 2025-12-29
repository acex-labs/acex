
from acex.acex import Acex


a = Acex(baseurl = "http://127.0.0.1/")



lns = a.logical_nodes()

for ln in lns:
    print(ln)


