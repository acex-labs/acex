# POC: Fysisk kabeldokumentation i Acex

## Syfte och kontext

Du ska bygga en ny modul i Acex för dokumentation av fysisk nätverksinfrastruktur — kablar, paneler, skåp och trunkar. Modulen lever som en egen sektion ("Fysisk planering") i Acex sidomeny, helt separat från befintlig funktionalitet men byggd med samma mönster och konventioner som resten av kodbasen.

Läs igenom befintlig kod innan du börjar skriva något. Förstå hur modeller definieras med SQLModel, hur migrationer sköts, hur FastAPI-routes är strukturerade, och hur React-komponenterna och routing är upplagda. Följ exakt samma mönster.

## Namngivning

Alla modeller, tabeller, routes och React-komponenter i den här modulen använder prefixet `Phys` (backend) och namnrymd `physical` (routes, filstruktur). Detta för att undvika kollisioner med befintliga begrepp i Acex — t.ex. är "port" och "fiber" sannolikt redan reserverade ord i nätverkskonfigurationsdelen.

Prefixet `Phys` används bara på entiteter som riskerar namnkollision med befintliga begrepp i nätverkskonfigurationsdelen — framför allt `Port`, `Fiber` och `Trunk`. `Room` och `Rack` är tillräckligt generiska för att stå utan prefix.

| Konceptuellt namn | Modellnamn (Python) | Tabellnamn (DB) | Route-prefix |
|---|---|---|---|
| Rum | `Room` | `physical_room` | `/physical/rooms` |
| Skåp/rack | `Rack` | `physical_rack` | `/physical/racks` |
| Panel | `PhysPanel` | `phys_panel` | `/physical/panels` |
| Panelport | `PhysPanelPort` | `phys_panel_port` | `/physical/panel-ports` |
| Fibertrunk | `PhysFiberTrunk` | `phys_fiber_trunk` | `/physical/fiber-trunks` |
| Enskild fiber | `PhysFiber` | `phys_fiber` | `/physical/fibers` |
| Korskoppling | `PhysCrossConnection` | `phys_cross_connection` | `/physical/cross-connections` |

React-komponenter namnges på samma vis: `PhysRackView`, `PhysPanelPortGrid`, `PhysFiberTrunkDetail` osv.

## Datamodell

Acex har redan en `Site`-modell. Bygg vidare på den — skapa inte en ny platsentitet.

### Entiteter att skapa

**Room** — rum inom en site
- `id`, `site_id` (FK → Site), `name`, `floor` (int), `description`

**Rack** — fysiskt skåp i ett rum
- `id`, `room_id` (FK → Room), `name`, `height_u` (int, antal U), `row`, `position`, `description`

**PhysPanel** — patch-panel, MPO-kassett, splicebox eller ODF monterad i rack
- `id`, `rack_id` (FK → Rack), `name`
- `panel_type`: enum — `patch`, `mpo`, `splice`, `odf`
- `connector_type`: enum — `lc`, `sc`, `mpo12`, `mpo24`
- `fiber_mode`: enum — `sm`, `mm_om3`, `mm_om4`
- `port_count` (int), `rack_unit` (int, vilket U den börjar på), `rack_unit_height` (int, hur många U den tar)

**PhysPanelPort** — enskild port på en panel
- `id`, `panel_id` (FK → PhysPanel), `port_number` (int), `label`, `polarity` (enum: `a`, `b`, `none`), `status` (enum: `active`, `reserve`, `disabled`)
- Panelportar skapas automatiskt när en panel skapas, baserat på `port_count`

**PhysFiberTrunk** — fysisk fiberkabel mellan två paneler
- `id`, `name`, `panel_a_id` (FK → PhysPanel), `panel_b_id` (FK → PhysPanel)
- `fiber_count` (int), `fiber_type` (enum: `os2`, `om3`, `om4`), `connector_type` (enum: `mpo12`, `mpo24`, `lc`, `sc`)
- `length_m` (float), `route_description`, `installed_at` (date)

**PhysFiber** — enskild fiber inom en fibertrunk
- `id`, `trunk_id` (FK → PhysFiberTrunk), `fiber_number` (int), `color` (string, TIA-598 färgkod), `attenuation_db` (float, nullable), `status` (enum: `active`, `reserve`, `broken`)
- Fibrer skapas automatiskt när en fibertrunk skapas, baserat på `fiber_count`

**PhysCrossConnection** — kopplar en panelport till en annan, valfritt via en specifik fiber
- `id`, `port_from_id` (FK → PhysPanelPort), `port_to_id` (FK → PhysPanelPort), `fiber_id` (FK → PhysFiber, nullable), `label`, `description`, `created_at`

### Framtida utökning (implementera ej nu, men förbered datamodellen)
Lägg till ett nullable fält `switchport_id` på `PhysPanelPort` som FK mot den modell i Acex som representerar switchportar (om en sådan finns). Om ingen sådan modell finns, hoppa över fältet. Detta för att i framtiden kunna trace:a hela vägen från nätverkskonfiguration till fysisk fiber.

## Arbetsordning — feature för feature

Bygg en feature i taget, hela vägen från databas till UI, innan du går vidare till nästa. Ordningen:

### 1. Grundstruktur och navigation
- Skapa migrationer för alla entiteter ovan
- Lägg till "Fysisk planering" i Acex sidomeny
- Skapa en tom landningssida som rooten för modulen

### 2. Platshierarki — rum och skåp
- CRUD-endpoints för `Room` (under befintlig Site)
- CRUD-endpoints för `Rack`
- React-vyer: lista rum per site, skapa/redigera rum, lista rack per rum, skapa/redigera rack
- Rack-detaljvy ska visa en visuell rack-representation: en vertikal lista med U-nummer (1 till height_u) där monterade paneler markeras med sitt namn och färg baserat på panel_type. U-positioner som är tomma visas som grå platshållare.

### 3. Paneler och panelportar
- CRUD-endpoints för `PhysPanel`; vid skapande, auto-generera `PhysPanelPort`-objekt baserat på `port_count`
- Läs-endpoint för panelportar per panel
- React-vy: paneldetalj som visar alla panelportar som ett rutnät (liknande patchpanel-vy). Varje panelport visar nummer, label och status med färgkodning (aktiv = grön, reserv = grå, ur bruk = röd).
- Lägg till paneler i rack-vyn så de visas på rätt U-position

### 4. Fibertrunkar och fibrer
- CRUD-endpoints för `PhysFiberTrunk`; vid skapande, auto-generera `PhysFiber`-objekt med TIA-598 färgkodning
- Läs-endpoints för fibrer per fibertrunk
- React-vy: fibertrunk-detalj som visar alla fibrer som ett rutnät med färgprickar och status. Visa trunk-metadata (längd, typ, anslutna paneler) tydligt.

### 5. Korskopplingar
- CRUD-endpoints för `PhysCrossConnection`
- Skapa korskoppling: välj port_from och port_to (med sökbar dropdown som visar panel → panelport), välj valfritt en fiber
- Visa befintliga korskopplingar på panelport-vyn — en panelport som har en korskoppling ska tydligt visa vart den går

### 6. Trace-funktion
- GET-endpoint `/physical/trace/{panel_port_id}` som returnerar hela kedjan: panelport → korskoppling → fiber → fibertrunk → motpart-panel → motpart-panelport
- Visa resultatet i en enkel path-visualisering i React: en horisontell rad med steg som visar varje hop i kedjan

### 7. Topologigraf
- GET-endpoint som returnerar noder (paneler) och kanter (fibertrunkar) för en given site eller rum
- React-vy med en enkel grafritning (använd ett lämpligt bibliotek om ett redan finns i projektet, annars föreslå vilket som passar bäst). Noder färgkodas efter panel_type, kanter visar trunk-namn och fiber_count.

## Tekniska riktlinjer

- Följ exakt samma mönster för modeller, routes, schemas och React-komponenter som redan finns i Acex
- Alla nya routes samlas under prefixet `/physical/`
- Alla nya DB-tabeller har prefixet `phys_`
- Alla nya Python-modeller och React-komponenter har prefixet `Phys`
- Inga magic strings — använd enums genomgående
- Felhantering och validering ska följa samma mönster som befintliga endpoints
- Skriv inte om befintlig kod — lägg till bredvid

## Vad du INTE ska bygga i denna POC
- Koppling mot aktiv utrustning (switchar, transceivrar) utöver det nullable fältet på PhysPanelPort
- Import/export av data
- Historik eller ändringslogg
- Behörighetsstyrning utöver vad som redan finns i Acex

## Starta här
Läs igenom kodbasen. Börja sedan med feature 1 — migrationer och navigation. Fråga om något är oklart innan du skriver kod.