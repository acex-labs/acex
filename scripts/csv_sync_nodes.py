import argparse
import csv
import sys
from dataclasses import dataclass

from pydantic import ValidationError

from acex_client import Acex
from acex_client.auth import NullAuthProvider

_VALID_STATUSES = {"planned", "init", "active", "decommissioned"}
_VALID_CONNECTION_TYPES = {"ssh", "telnet"}


@dataclass
class ColumnMap:
    hostname: str = "hostname"
    role: str = "role"
    site: str = "site"
    sequence: str = "sequence"
    vendor: str = "vendor"
    serial_number: str = "serial_number"
    os: str = "os"
    os_version: str = "os_version"
    hardware_model: str = "hardware_model"
    ned_id: str = "ned_id"
    status: str = "status"
    management_ip: str = "management_ip"
    connection_type: str = "connection_type"


# Helpers
def _str_or_none(value: str) -> str | None:
    stripped = value.strip()
    return stripped if stripped else None


def _int_or_none(value: str) -> int | None:
    try:
        return int(value.strip()) if value.strip() else None
    except ValueError:
        return None


def _validate_status(value: str | None) -> tuple[str, str | None]:
    if not value:
        return "planned", None
    lower = value.lower()
    if lower not in _VALID_STATUSES:
        return "planned", f"unrecognized status '{value}' — using 'planned'"
    return lower, None


def _validate_connection_type(value: str | None) -> tuple[str, str | None]:
    if not value:
        return "ssh", None
    lower = value.lower()
    if lower not in _VALID_CONNECTION_TYPES:
        return "ssh", f"unrecognized connection_type '{value}' — using 'ssh'"
    return lower, None


def _diff(existing_obj, body: dict) -> dict:
    return {
        field: (getattr(existing_obj, field, None), new_val)
        for field, new_val in body.items()
        if getattr(existing_obj, field, None) != new_val
    }


def _build_site_map(
    sites_csv: str,
    delimiter: str,
    sites_col_key: str,
    sites_col_name: str,
) -> dict[str, str]:
    with open(sites_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        return {
            key: name
            for row in reader
            if (key := _str_or_none(row.get(sites_col_key, "")))
            and (name := _str_or_none(row.get(sites_col_name, "")))
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

    def log_changes(self, subject: str, resource: str, changes: dict) -> None:
        for field, (old, new) in changes.items():
            self.changed(subject, f"{resource}.{field}", old, new)

    def unchanged(self, subject: str) -> None:
        print(f"  =     {subject} unchanged")

    def error(self, subject: str, context: str, exc: Exception) -> None:
        print(f"  ERROR {subject} ({context}): {exc}")

    def decommissioned(self, subject: str, dry_run: bool = False) -> None:
        prefix = "[dry-run] " if dry_run else ""
        print(f"  ~     {prefix}{subject}: node_instance.status → 'decommissioned'")

    def summary(self, created: int, updated: int, skipped: int, errors: int, decommissioned: int = 0) -> None:
        parts = [f"created: {created}", f"updated: {updated}", f"skipped: {skipped}", f"errors: {errors}"]
        if decommissioned:
            parts.append(f"decommissioned: {decommissioned}")
        print(f"\nDone — {', '.join(parts)}")


# Syncer
class NodeSyncer:
    def __init__(self, client, cols: ColumnMap, site_map: dict[str, str], log: SyncLogger | None = None):
        self.client = client
        self.cols = cols
        self.site_map = site_map
        self.log = log or SyncLogger()
        self.existing_sites: set[str] = set()
        self.existing_logical_nodes: dict = {}
        self.existing_assets: dict = {}
        self.existing_node_instances: dict = {}
        self.existing_mgmt: dict = {}

    def prefetch(self) -> None:
        c = self.client
        self.existing_sites = {s.name for s in c.inventory.sites.query(limit=10000).items}
        self.existing_logical_nodes = {ln.hostname: ln for ln in c.inventory.logical_nodes.query(limit=10000).items}
        self.existing_assets = {a.serial_number: a for a in c.inventory.assets.query(limit=10000).items}
        self.existing_node_instances = {ni.logical_node_id: ni for ni in c.inventory.node_instances.query(limit=10000).items}
        self.existing_mgmt = {mc.node_id: mc for mc in c.inventory.management_connections.query(limit=10000).items}
        print(
            f"Found {len(self.existing_logical_nodes)} logical nodes, "
            f"{len(self.existing_assets)} assets, "
            f"{len(self.existing_node_instances)} node instances\n"
        )

    def _resolve_site(self, hostname: str, raw: str | None) -> str | None:
        if not raw:
            return None
        if self.site_map:
            site = self.site_map.get(raw)
            if not site:
                self.log.warn(hostname, f"no site mapping for '{raw}' — site will be null")
            return site
        if raw not in self.existing_sites:
            self.log.warn(hostname, f"site '{raw}' not found in ACEX")
        return raw

    def _sync_logical_node(self, hostname: str, body: dict) -> tuple:
        safe_body = {k: v for k, v in body.items() if not (k == "role" and v is None)}
        if hostname in self.existing_logical_nodes:
            ln = self.existing_logical_nodes[hostname]
            changes = _diff(ln, safe_body)
            if changes:
                self.client.inventory.logical_nodes.update(id=ln.id, **safe_body)
                self.log.log_changes(hostname, "logical_node", changes)
                return ln, False, True
            return ln, False, False
        ln = self.client.inventory.logical_nodes.create(hostname=hostname, **safe_body)
        self.existing_logical_nodes[hostname] = ln
        self.log.created(hostname, "logical node")
        return ln, True, False

    def _sync_asset(self, hostname: str, serial_number: str, body: dict) -> tuple:
        update_body = {k: v for k, v in body.items() if k != "serial_number" and v is not None}
        create_body = {k: v for k, v in body.items() if v is not None}
        if serial_number in self.existing_assets:
            asset = self.existing_assets[serial_number]
            changes = _diff(asset, update_body)
            if changes:
                self.client.inventory.assets.update(id=asset.id, **update_body)
                self.log.log_changes(hostname, "asset", changes)
                return asset, True
            return asset, False
        asset = self.client.inventory.assets.create(**create_body)
        self.existing_assets[serial_number] = asset
        self.log.created(hostname, f"asset {serial_number}")
        return asset, False

    def _sync_node_instance(self, hostname: str, asset, ln_id: int, status: str) -> tuple:
        if ln_id in self.existing_node_instances:
            ni = self.existing_node_instances[ln_id]
            if ni.status != status:
                self.client.inventory.node_instances.update(id=ni.id, status=status)
                self.log.changed(hostname, "node_instance.status", ni.status, status)
                return ni, True
            return ni, False
        try:
            ni = self.client.inventory.node_instances.create(
                asset_ref_id=asset.id,
                asset_ref_type="asset",
                logical_node_id=ln_id,
                status=status,
            )
        except ValidationError:
            # Backend create succeeds but response lacks nested asset/logical_node;
            # fall back to the list endpoint which uses the simpler NodeListItem model.
            result = self.client.inventory.node_instances.query(logical_node_id=ln_id)
            if not result.items:
                raise Exception(f"node instance not found after creation (logical_node_id={ln_id})")
            ni = result.items[0]
        self.existing_node_instances[ln_id] = ni
        self.log.created(hostname, "node instance")
        return ni, False

    def _sync_management_connection(self, hostname: str, ni_id: int, management_ip: str, connection_type: str) -> bool:
        body = {"target_ip": management_ip, "connection_type": connection_type}
        if ni_id in self.existing_mgmt:
            mc = self.existing_mgmt[ni_id]
            changes = _diff(mc, body)
            if changes:
                self.client.inventory.management_connections.update(id=mc.id, **body)
                self.log.log_changes(hostname, "management_connection", changes)
                return True
            return False
        self.client.inventory.management_connections.rest.request(
            "POST",
            "/inventory/management_connections/",
            json={"node_id": ni_id, "primary": True, **body},
        )
        self.log.created(hostname, f"management connection {management_ip} ({connection_type})")
        return False

    def decommission_missing(self, seen_hostnames: set[str], dry_run: bool = False) -> int:
        count = 0
        for hostname, ln in self.existing_logical_nodes.items():
            if hostname in seen_hostnames:
                continue
            ni = self.existing_node_instances.get(ln.id)
            if ni is None:
                continue
            if ni.status == "decommissioned":
                continue
            if dry_run:
                self.log.decommissioned(hostname, dry_run=True)
            else:
                try:
                    self.client.inventory.node_instances.update(id=ni.id, status="decommissioned")
                    self.log.decommissioned(hostname)
                except Exception as e:
                    self.log.error(hostname, "decommission", e)
                    continue
            count += 1
        return count

    def sync_row(self, row: dict, hostname: str, serial_number: str) -> tuple[bool, bool, int]:
        cols = self.cols
        site = self._resolve_site(hostname, _str_or_none(row.get(cols.site, "")))
        status, status_warn = _validate_status(_str_or_none(row.get(cols.status, "")))
        if status_warn:
            self.log.warn(hostname, status_warn)
        connection_type, ct_warn = _validate_connection_type(_str_or_none(row.get(cols.connection_type, "")))
        if ct_warn:
            self.log.warn(hostname, ct_warn)
        management_ip = _str_or_none(row.get(cols.management_ip, ""))

        ln_body = {
            "role": _str_or_none(row.get(cols.role, "")),
            "site": site,
            "sequence": _int_or_none(row.get(cols.sequence, "")),
        }
        asset_body = {
            "vendor": _str_or_none(row.get(cols.vendor, "")),
            "serial_number": serial_number,
            "os": _str_or_none(row.get(cols.os, "")),
            "os_version": _str_or_none(row.get(cols.os_version, "")),
            "hardware_model": _str_or_none(row.get(cols.hardware_model, "")),
            "ned_id": _str_or_none(row.get(cols.ned_id, "")),
        }

        _, is_new, ln_changed = self._sync_logical_node(hostname, ln_body)
        asset, asset_changed = self._sync_asset(hostname, serial_number, asset_body)
        ln_id = self.existing_logical_nodes[hostname].id
        ni, ni_changed = self._sync_node_instance(hostname, asset, ln_id, status)

        mgmt_changed = False
        if management_ip:
            mgmt_changed = self._sync_management_connection(hostname, ni.id, management_ip, connection_type)

        return is_new, ln_changed or asset_changed or ni_changed or mgmt_changed, ni.id


# Entry point
def sync_nodes(
    csv_path: str,
    base_url: str,
    delimiter: str = ",",
    cols: ColumnMap | None = None,
    sites_csv: str | None = None,
    sites_delimiter: str | None = None,
    sites_col_key: str = "id",
    sites_col_name: str = "id",
    decommission_missing: bool = False,
    dry_run: bool = False,
) -> None:
    if cols is None:
        cols = ColumnMap()

    site_map: dict[str, str] = {}
    if sites_csv:
        site_map = _build_site_map(sites_csv, sites_delimiter or delimiter, sites_col_key, sites_col_name)
        print(f"Loaded {len(site_map)} site mappings from {sites_csv}\n")

    client = Acex(base_url=base_url, auth=NullAuthProvider(), verify=False)
    log = SyncLogger()
    syncer = NodeSyncer(client, cols, site_map, log)
    syncer.prefetch()

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=delimiter))
    print(f"Read {len(rows)} rows from {csv_path}\n")

    created = updated = skipped = errors = 0
    seen_hostnames: set[str] = set()

    for row in rows:
        hostname = _str_or_none(row.get(cols.hostname, ""))
        serial_number = _str_or_none(row.get(cols.serial_number, ""))

        if not hostname:
            log.skip(f"row with empty {cols.hostname}", "")
            skipped += 1
            continue
        if not serial_number:
            log.skip(hostname, f"empty {cols.serial_number}")
            skipped += 1
            continue

        seen_hostnames.add(hostname)

        try:
            is_new, changed = syncer.sync_row(row, hostname, serial_number)
        except Exception as e:
            log.error(hostname, "sync", e)
            errors += 1
            continue

        if is_new:
            created += 1
        elif changed:
            updated += 1
        else:
            skipped += 1
            log.unchanged(hostname)

    decommissioned = 0
    if decommission_missing:
        if dry_run:
            print("\nDry run — nodes that would be decommissioned:")
        else:
            print("\nDecommissioning nodes not present in CSV...")
        decommissioned = syncer.decommission_missing(seen_hostnames, dry_run=dry_run)

    log.summary(created, updated, skipped, errors, decommissioned)
    if errors:
        sys.exit(1)

# Main function and CLI
def main() -> None:
    parser = argparse.ArgumentParser(description="Sync nodes from a CSV file into ACEX")
    parser.add_argument("--csv", required=True, help="Path to CSV file")
    parser.add_argument("--base-url", default="http://localhost:80", help="ACEX API base URL")
    parser.add_argument("--delimiter", default=",", help="CSV delimiter (default: ',')")
    parser.add_argument("--decommission-missing", action="store_true",
                        help="Mark nodes in ACEX not present in the CSV as decommissioned")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be decommissioned without making any changes (requires --decommission-missing)")

    s = parser.add_argument_group("site join", "Resolve site name via a second CSV (optional)")
    s.add_argument("--sites-csv", metavar="PATH", help="Sites CSV used to resolve site names")
    s.add_argument("--sites-delimiter", metavar="DELIM", help="Delimiter for sites CSV (default: same as --delimiter)")
    s.add_argument("--sites-col-key", default="id", metavar="COL", help="Column in sites CSV to join on (default: id)")
    s.add_argument("--sites-col-name", default="id", metavar="COL", help="Column in sites CSV that contains the ACEX site name (default: id)")

    g = parser.add_argument_group("column mapping", "Override CSV column names")
    g.add_argument("--col-hostname", default="hostname", metavar="COL")
    g.add_argument("--col-role", default="role", metavar="COL")
    g.add_argument("--col-site", default="site", metavar="COL")
    g.add_argument("--col-sequence", default="sequence", metavar="COL")
    g.add_argument("--col-vendor", default="vendor", metavar="COL")
    g.add_argument("--col-serial-number", default="serial_number", metavar="COL")
    g.add_argument("--col-os", default="os", metavar="COL")
    g.add_argument("--col-os-version", default="os_version", metavar="COL")
    g.add_argument("--col-hardware-model", default="hardware_model", metavar="COL")
    g.add_argument("--col-ned-id", default="ned_id", metavar="COL")
    g.add_argument("--col-status", default="status", metavar="COL")
    g.add_argument("--col-management-ip", default="management_ip", metavar="COL")
    g.add_argument("--col-connection-type", default="connection_type", metavar="COL")

    args = parser.parse_args()

    sync_nodes(
        args.csv,
        args.base_url,
        args.delimiter,
        decommission_missing=args.decommission_missing,
        dry_run=args.dry_run,
        cols=ColumnMap(
            hostname=args.col_hostname,
            role=args.col_role,
            site=args.col_site,
            sequence=args.col_sequence,
            vendor=args.col_vendor,
            serial_number=args.col_serial_number,
            os=args.col_os,
            os_version=args.col_os_version,
            hardware_model=args.col_hardware_model,
            ned_id=args.col_ned_id,
            status=args.col_status,
            management_ip=args.col_management_ip,
            connection_type=args.col_connection_type,
        ),
        sites_csv=args.sites_csv,
        sites_delimiter=args.sites_delimiter,
        sites_col_key=args.sites_col_key,
        sites_col_name=args.sites_col_name,
    )


if __name__ == "__main__":
    main()
