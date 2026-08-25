import argparse
import csv
import sys
from dataclasses import dataclass

import pycountry
from acex_client import Acex
from acex_client.auth import NullAuthProvider


@dataclass
class ColumnMap:
    id: str = "id"
    type: str = "type"
    address: str = "address"
    city: str = "city"
    country: str = "country"
    latitude: str = "latitude"
    longitude: str = "longitude"
    description: str = "description"
    continent: str = "continent"


# Field helpers
def _float_or_none(value: str) -> float | None:
    try:
        return float(value) if value.strip() else None
    except ValueError:
        return None


def _str_or_none(value: str) -> str | None:
    stripped = value.strip()
    return stripped if stripped else None


_CONTINENT_ALIASES: dict[str, str] = {
    "AFRICA": "Africa", "AF": "Africa", "AFR": "Africa",
    "ANTARCTICA": "Antarctica", "AN": "Antarctica", "ANT": "Antarctica",
    "ASIA": "Asia", "AS": "Asia",
    "EUROPE": "Europe", "EU": "Europe", "EUR": "Europe",
    "NORTH AMERICA": "North America", "NA": "North America", "NAM": "North America",
    "OCEANIA": "Oceania", "OC": "Oceania", "OCE": "Oceania",
    "SOUTH AMERICA": "South America", "SA": "South America", "SAM": "South America",
}


def _normalize_continent(value: str) -> str | None:
    return _CONTINENT_ALIASES.get(value.strip().upper())


def _normalize_country(value: str) -> tuple[str | None, bool]:
    stripped = value.strip()
    if not stripped:
        return None, True
    upper = stripped.upper()
    country = (
        pycountry.countries.get(alpha_2=upper)
        or pycountry.countries.get(alpha_3=upper)
        or pycountry.countries.get(name=stripped)
        or pycountry.countries.get(common_name=stripped)
        or pycountry.countries.get(official_name=stripped)
        or next((c for c in pycountry.countries if c.name.upper() == upper), None)
    )
    if country:
        return country.name, True
    return stripped, False


def _display_name(row: dict, cols: ColumnMap) -> str | None:
    city = row.get(cols.city, "").strip()
    site_type = row.get(cols.type, "").strip()
    if city and site_type:
        return f"{city} {site_type}"
    return city or site_type or None


_SYNCABLE_FIELDS = ("display_name", "address", "city", "country", "latitude", "longitude", "description")


def _site_body(row: dict, cols: ColumnMap) -> dict:
    return {
        "display_name": _display_name(row, cols),
        "address": _str_or_none(row.get(cols.address, "")),
        "city": _str_or_none(row.get(cols.city, "")),
        "country": _str_or_none(row.get(cols.country, "")),
        "latitude": _float_or_none(row.get(cols.latitude, "")),
        "longitude": _float_or_none(row.get(cols.longitude, "")),
        "description": _str_or_none(row.get(cols.description, "")),
    }


def _diff(existing, body: dict) -> dict:
    return {
        field: (getattr(existing, field, None), body[field])
        for field in _SYNCABLE_FIELDS
        if getattr(existing, field, None) != body[field]
    }


# Logger
class SyncLogger:
    def skip(self, subject: str, reason: str) -> None:
        print(f"  SKIP  {subject}: {reason}")

    def warn(self, subject: str, message: str) -> None:
        print(f"  WARN  {subject}: {message}")

    def created(self, subject: str, detail: str = "") -> None:
        suffix = f" ({detail})" if detail else ""
        print(f"  +     {subject}{suffix}")

    def changed(self, subject: str, field: str, old, new) -> None:
        print(f"  ~     {subject}: {field} {old!r} → {new!r}")

    def log_changes(self, subject: str, changes: dict) -> None:
        for field, (old, new) in changes.items():
            self.changed(subject, field, old, new)

    def unchanged(self, subject: str) -> None:
        print(f"  =     {subject} unchanged")

    def error(self, subject: str, context: str, exc: Exception) -> None:
        print(f"  ERROR {subject} ({context}): {exc}")

    def summary(self, created: int, updated: int, skipped: int, errors: int) -> None:
        print(f"\nDone — created: {created}, updated: {updated}, skipped: {skipped}, errors: {errors}")


# Syncer
class SiteSyncer:
    def __init__(self, client, cols: ColumnMap, log: SyncLogger | None = None):
        self.client = client
        self.cols = cols
        self.log = log or SyncLogger()
        self.existing_sites: dict = {}
        self.existing_assignments: set[tuple] = set()

    def prefetch(self) -> None:
        self.existing_sites = {s.name: s for s in self.client.inventory.sites.query(limit=10000).items}
        self.existing_assignments = {
            (a.region_name, a.site_name)
            for a in self.client.inventory.region_assignments.query(limit=10000).items
        }
        print(f"Found {len(self.existing_sites)} existing sites in ACEX\n")

    def sync_regions(self, rows: list[dict]) -> None:
        existing = {r.name for r in self.client.inventory.regions.query(limit=10000).items}
        continents: set[str] = set()
        unrecognized: set[str] = set()

        for row in rows:
            raw = row.get(self.cols.continent, "").strip()
            if not raw:
                continue
            normalized = _normalize_continent(raw)
            if normalized:
                continents.add(normalized)
            else:
                unrecognized.add(raw)

        for value in sorted(unrecognized):
            self.log.warn(f"continent '{value}'", "unrecognized — skipping region and assignment for affected sites")

        for continent in sorted(continents):
            if continent in existing:
                self.log.unchanged(f"region '{continent}'")
            else:
                try:
                    self.client.inventory.regions.create(name=continent, display_name=continent)
                    self.log.created(f"region '{continent}'")
                    existing.add(continent)
                except Exception as e:
                    self.log.error(f"region '{continent}'", "create", e)

    def _assign_region(self, site_name: str, continent: str | None) -> None:
        if not continent:
            return
        if (continent, site_name) in self.existing_assignments:
            return
        try:
            self.client.inventory.region_assignments.create(region_name=continent, site_name=site_name)
            self.existing_assignments.add((continent, site_name))
        except Exception as e:
            self.log.warn(f"region assignment {site_name} → {continent}", str(e))

    def sync_row(self, row: dict) -> tuple[bool, bool]:
        cols = self.cols
        name = _str_or_none(row.get(cols.id, ""))
        assert name is not None
        raw_continent = row.get(cols.continent, "").strip()
        continent = _normalize_continent(raw_continent) if raw_continent else None

        body = _site_body(row, cols)

        lat, lon = body.get("latitude"), body.get("longitude")
        if lat is not None and not (-90 <= lat <= 90):
            self.log.warn(name, f"latitude {lat} out of range [-90, 90] — setting to null")
            body["latitude"] = None
        if lon is not None and not (-180 <= lon <= 180):
            self.log.warn(name, f"longitude {lon} out of range [-180, 180] — setting to null")
            body["longitude"] = None

        raw_country = body.get("country")
        if raw_country:
            normalized_country, recognized = _normalize_country(raw_country)
            if not recognized:
                self.log.warn(name, f"unrecognized country '{raw_country}' — storing as-is")
            else:
                body["country"] = normalized_country

        if name in self.existing_sites:
            changes = _diff(self.existing_sites[name], body)
            if changes:
                try:
                    self.client.inventory.sites.update(id=self.existing_sites[name].id, **body)
                except Exception as e:
                    self.log.error(name, "update", e)
                    raise
                self.log.log_changes(name, changes)
                self._assign_region(name, continent)
                return False, True
            self.log.unchanged(name)
            self._assign_region(name, continent)
            return False, False

        try:
            self.client.inventory.sites.create(name=name, **body)
        except Exception as e:
            self.log.error(name, "create", e)
            raise
        self.log.created(name, body.get("display_name") or "")
        self._assign_region(name, continent)
        return True, False


# Public entry point
def sync_sites(csv_path: str, base_url: str, delimiter: str = ",", cols: ColumnMap | None = None) -> None:
    if cols is None:
        cols = ColumnMap()

    client = Acex(base_url=base_url, auth=NullAuthProvider(), verify=False)
    log = SyncLogger()
    syncer = SiteSyncer(client, cols, log)

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=delimiter))
    print(f"Read {len(rows)} rows from {csv_path}\n")

    print("Syncing regions...")
    syncer.sync_regions(rows)
    print()

    syncer.prefetch()

    created = updated = skipped = errors = 0

    for row in rows:
        name = _str_or_none(row.get(cols.id, ""))
        if not name:
            log.skip(f"row with empty {cols.id}", "")
            skipped += 1
            continue

        try:
            is_new, changed = syncer.sync_row(row)
        except Exception:
            errors += 1
            continue

        if is_new:
            created += 1
        elif changed:
            updated += 1
        else:
            skipped += 1

    log.summary(created, updated, skipped, errors)
    if errors:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync sites from a CSV file into ACEX")
    parser.add_argument("--csv", required=True, help="Path to CSV file")
    parser.add_argument("--base-url", default="http://localhost:80", help="ACEX API base URL")
    parser.add_argument("--delimiter", default=",", help="CSV delimiter (default: ',')")

    g = parser.add_argument_group("column mapping", "Override CSV column names (defaults match Enet export)")
    g.add_argument("--col-id", default="id", metavar="COL", help="Site identifier column (default: id)")
    g.add_argument("--col-type", default="type", metavar="COL", help="Site type column, used in display name (default: type)")
    g.add_argument("--col-address", default="address", metavar="COL")
    g.add_argument("--col-city", default="city", metavar="COL")
    g.add_argument("--col-country", default="country", metavar="COL")
    g.add_argument("--col-latitude", default="latitude", metavar="COL")
    g.add_argument("--col-longitude", default="longitude", metavar="COL")
    g.add_argument("--col-description", default="description", metavar="COL", help="Description column (default: description)")
    g.add_argument("--col-continent", default="continent", metavar="COL", help="Continent/region column (default: continent)")

    args = parser.parse_args()

    cols = ColumnMap(
        id=args.col_id,
        type=args.col_type,
        address=args.col_address,
        city=args.col_city,
        country=args.col_country,
        latitude=args.col_latitude,
        longitude=args.col_longitude,
        description=args.col_description,
        continent=args.col_continent,
    )

    sync_sites(args.csv, args.base_url, args.delimiter, cols)


if __name__ == "__main__":
    main()