# PnP via DHCP — plan och status

## Mål

Funktionalitet för Plug-and-Play (PnP) via DHCP. Först för Cisco-enheter,
men arkitekturen ska vara vendor-agnostisk. Enheten får en **initial
bootstrap-config** som gör den nåbar via SSH, varefter vanlig provision
lägger på full konfiguration.

## Flöde (happy path)

```
1. Integratör/kund: POST /pnp/claims {serial_number, hostname, mgmt:{...}, asset_id?}
2. Switch bootar → DHCP → option 66/67 pekar på ACEX (TFTP/HTTP)
3. Switch: GET /pnp/bootstrap/config?serial=FOC1234
4. PnpManager: slå upp claim → bygg BootstrapProfile → NED.render_bootstrap(profile, asset)
5. Switch applicerar bootstrap → är nu nåbar via SSH (mgmt-VLAN + användare + ssh keys)
6. Switch/ACEX: POST /pnp/claims/{serial}/complete (eller ACEX verifierar SSH-reachability)
7. Vanlig provision tar över: compila full config → render → push via SSH (existerande transport)
```

**Viktigt designbeslut:** Bootstrap är inte en `ComposedConfiguration`. Det
är en egen, tunnare kanal. Full config beror på hela inventory-kontextet
(site, logical node, config maps) som ofta inte är på plats förrän enheten
identifierats och claimats. Bootstrap ska bara ge SSH-reachability.

## Gjort hittills (denna branch)

### devkit

- **`acex_devkit/models/bootstrap.py`** (ny): `BootstrapProfile` och
  `BootstrapUser` — vendor-agnostisk modell för allt som behövs för att
  rendera en initial config (hostname, management-interface, users, SSH,
  domain, DNS, NTP). `management` är medvetet free-form (`dict`) eftersom
  varje driver/template tolkar det själv.
- **`acex_devkit/models/__init__.py`**: exporterar `BootstrapProfile`,
  `BootstrapUser`.
- **`acex_devkit/drivers/base.py`**: `NetworkElementDriver.render_bootstrap(profile, asset)`
  — opt-in hook per driver (default `NotImplementedError`), samma mönster
  som `TransportBase.execute()` och `get_lldp_neighbors()`.
  (Notering: `base_driver.py` är en död parallell fil som inte importeras —
  ändringen ligger i `base.py`.)

## Plan — resterande delar

### 1. Claim-modell (backend, `acex.pnp`)

```python
class PnpClaimStatus(StrEnum):
    PENDING = "pending"            # claim skapad, enheten har inte dykt upp
    BOOTSTRAPPED = "bootstrapped"  # bootstrap-config har hämtats
    PROVISIONED = "provisioned"    # full config på plats
    EXPIRED = "expired"

class PnpClaim(BaseModel):  # eller SQLModel, se fråga 1
    serial_number: str
    hostname: str
    ned_id: str | None          # bestämmer vilken driver som renderar bootstrap
    asset_id: int | None        # länk till inventory om asset redan finns
    management: dict            # t.ex. {"interface": "Vlan123", "vlan_id": 123, "dhcp": true}
    users: list[BootstrapUser]
    status: PnpClaimStatus
```

`ned_id` är nyckeln till vendor-agnosticiteten: managern vet inget om
Cisco, den hämtar bara drivern och anropar `render_bootstrap`. En framtida
Juniper-ZTP-driver påverkar inte backend alls.

### 2. PnpManager

```python
class PnpManager:
    def create_claim(claim) -> PnpClaim
    def get_claim(serial) -> PnpClaim
    def list_claims(status=None)
    def render_bootstrap(serial) -> str:
        claim = self.get_claim(serial)          # 404 om ingen claim
        driver = self.neds.get_driver_instance(claim.ned_id)
        profile = BootstrapProfile(...)         # vendor-agnostisk
        return driver.render_bootstrap(profile, asset)
        # + markera claim som BOOTSTRAPPED
```

Registreras i `AutomationEngine` som `self.pnp_manager`.

### 3. API (`backend/src/acex/api/routers/pnp.py`)

```
POST   /api/v1/pnp/claims              # skapa claim
GET    /api/v1/pnp/claims              # lista (filter: status)
GET    /api/v1/pnp/claims/{serial}     # visa claim
DELETE /api/v1/pnp/claims/{serial}
GET    /api/v1/pnp/bootstrap/{serial}  # renderad bootstrap-config (text/plain)
                                       # ← URL:en som DHCP option 67 pekar på
POST   /api/v1/pnp/claims/{serial}/complete  # markera klar → trigga provision
```

Routern följer mönstret från `management_connections.py` och kopplas upp
automatiskt av `api.py`:s glob-loop över `routers/`.

### 4. Cisco-drivern

`render_bootstrap()` på `CiscoIOSCLIDriver` + dedikerad `bootstrap.j2`
(separerad från `template.j2` — bootstrap ska inte ärva all logik i full
render). Konceptuellt:

```
hostname {{ profile.hostname }}
!
{% if profile.management.dhcp %}
interface Vlan{{ profile.management.vlan_id }}
 ip address dhcp
 no shutdown
{% endif %}
!
ip domain-name {{ profile.domain_name }}
username {{ u.username }} privilege 15 secret {{ u.password }}
!
ip ssh version 2
line vty 0 15
 transport input ssh
 login local
!
end
```

**Cisco-fallgrop:** `crypto key generate rsa` är interaktivt och kan inte
bara klistras in i en config-fil. Vanliga fältmönstret är en **EEM-applet**
i bootstrap-configen som genererar RSA-nyckeln vid första boot och sedan
tar bort sig själv.

### 5. DHCP — vad vi INTE bygger

ACEX ska inte vara DHCP-server. Kundens DHCP (ISC, Kea, IOS, Windows)
konfigureras en gång per PnP-VLAN och pekar mot ACEX via option 66/67.
Eventuell framtida feature: generera DHCP-server-stubbar (`kea`/`isc`)
från claims — nice-to-have, inte del av första slicen.

### 6. Worker/provision-handoff

`complete` markeras och en worker/integration plockar upp enheten för full
provision (compila → render → push via existerande SSH-transport). Hålls
lös i första slicen.

## Öppna frågor att svara

1. **Persistence för claims:** SQLModel-tabell direkt, eller in-memory först?
   Förslag: SQLModel direkt — billigt (samma mönster som
   `ManagementConnection`) och claims måste överleva omstarter (en switch
   kan boota om mitt i flödet).

2. **Bootstrap-URL och filnamnsmönster:** Cisco Autoinstall försöker hämta
   `network-confg`, `cisconet.cfg`, `<hostname>-confg` i sekvens. Ska vi
   stödja det klassiska mönstret (`GET /pnp/bootstrap/files/{filename}`
   som mappar `<hostname>-confg` → claim), eller explicit option 67 per
   enhet (kräver DHCP-reservationer)? Det första är mer "plug and play",
   det andra mer kontrollerat.

3. **Matchning switch → claim:** Serienummer i URL:en förutsätter unik
   bootfile per enhet. Alternativ: **generisk bootstrap per pool** (alla
   får samma config, hostname via DHCP option 12) där identiteten
   etableras först när switchen rapporterar in. Generisk-per-pool kräver
   noll per-enhet-DHCP-config; explicit-per-serial är säkrare.

4. **Handoff till provision (steg 6→7):** Ska `complete` bara markera
   status, eller trigga något direkt (skapa Node i inventory, compila,
   pusha)? Förslag första slicen: bara status + en `provision_hint`
   (t.ex. logical_node_id) som en worker/integration kan plocka upp.

5. **Credentials i bootstrap:** Lösenord i klartext i claim-payloaden?
   Vi har `CredentialManager` med kryptering, men bootstrap-configen måste
   ändå innehålla secret i klar- eller hashtext. Förslag: acceptera
   redan-hashade IOS type-8/9-secrets i claimet, så ligger inga
   klartextlösenord i databasen.

## Förslag på default-val om inget annat sägs

| Fråga | Default |
|---|---|
| Persistence | SQLModel-tabell |
| Filnamnsmönster | Explicit URL per serial (option 67) |
| Matchning | Per-serial claim |
| Handoff | Bara status + provision_hint |
| Credentials | Hashade secrets (IOS type 8/9) |
