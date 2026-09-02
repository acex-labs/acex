from acex_client import Acex


client = Acex(
    base_url="https://acex.auto.ngninfra.net",
    verify=False
)


sites = client.inventory.sites.query(limit=1000)

print(sites)