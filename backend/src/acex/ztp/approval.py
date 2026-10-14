"""What approving a discovery does to the asset with its serial, and doing it.

The listing, the dry run and the approval itself all plan through
`ApprovalPlanner`, so what an administrator sees is what gets written.
"""

import hashlib
import json

from acex.models.asset import Asset
from acex.models.ztp_discovery import ZtpDiscovery
from acex.ztp.review_context import ReviewContext
from acex_devkit.models.asset import Asset as AssetSchema
from acex_devkit.models.platform import OS, Vendor
from acex_devkit.models.ztp import ZtpApprovalAction, ZtpApprovalProposal, ZtpFactChange, ZtpProposedAsset
from pydantic import ValidationError

#: What a new asset cannot be created without.
_REQUIRED_FACTS = ("vendor", "os", "hardware_model")

#: The facts approval writes to an asset that already exists. The vendor is not
#: one of them: the same serial from another vendor is a reason to stop, not to update.
_UPDATED_FACTS = ("hardware_model", "os", "os_version")


class ApprovalPlanner:
    def __init__(self, ctx: ReviewContext):
        self.ctx = ctx

    def plan(self, discovery: ZtpDiscovery) -> ZtpApprovalProposal:
        """Create the asset, update it, leave it as it is, or refuse, and why."""
        matches = self.ctx.assets_with_serial(discovery)
        if len(matches) > 1:
            ids = ", ".join(str(a.id) for a in matches)
            return self._blocked(
                f"{len(matches)} assets have serial {discovery.serial_number} ({ids}); remove the duplicates"
            )

        vendor, os_ = self._enum(Vendor, discovery.vendor), self._enum(OS, discovery.os)
        blocked = [
            f"Reported {name} {value!r} is not one ACEX knows"
            for name, value, known in (("vendor", discovery.vendor, vendor), ("OS", discovery.os, os_))
            if value and known is None
        ]
        if not matches:
            return self._plan_create(discovery, vendor, os_, blocked)
        return self._plan_update(discovery, matches[0], vendor, os_, blocked)

    def apply(self, session, proposal: ZtpApprovalProposal) -> Asset:
        """Create or update the asset as the proposal says."""
        values = proposal.asset.model_dump() | {
            "vendor": Vendor(proposal.asset.vendor),
            "os": OS(proposal.asset.os),
        }
        if proposal.action == ZtpApprovalAction.create:
            asset = Asset(**values)
        else:
            asset = session.get(Asset, proposal.asset_id)
            for change in proposal.changes:
                setattr(asset, change.field, values[change.field])
        session.add(asset)
        session.flush()
        return asset

    def _plan_create(self, discovery, vendor, os_, blocked) -> ZtpApprovalProposal:
        blocked += [
            f"The device did not report its {fact.replace('_', ' ')}"
            for fact in _REQUIRED_FACTS
            if not getattr(discovery, fact)
        ]
        if blocked:
            return self._blocked(*blocked)
        try:
            valid = AssetSchema(
                vendor=vendor,
                serial_number=discovery.serial_number,
                os=os_,
                hardware_model=discovery.hardware_model,
                os_version=discovery.os_version,
                ned_id=self.ctx.ned_for(discovery),
            )
        except ValidationError as exc:
            return self._blocked(*self._messages(exc))
        return self._proposal(ZtpApprovalAction.create, asset=self._proposed(valid))

    def _plan_update(self, discovery, asset: Asset, vendor, os_, blocked) -> ZtpApprovalProposal:
        if vendor is not None and vendor != asset.vendor:
            blocked.append(f"Reported vendor {vendor} but asset {asset.id} is {asset.vendor}; check the asset")
        if blocked:
            return self._blocked(*blocked, asset_id=asset.id)

        reported = {"hardware_model": discovery.hardware_model, "os": os_, "os_version": discovery.os_version}
        merged = {name: getattr(asset, name) for name in ("vendor", "serial_number", "ned_id", *_UPDATED_FACTS)}
        merged |= {fact: value for fact, value in reported.items() if value is not None}
        try:
            valid = AssetSchema(**merged)
        except ValidationError as exc:
            return self._blocked(*self._messages(exc), asset_id=asset.id)

        changes = []
        for fact in _UPDATED_FACTS:
            current, new = self._text(getattr(asset, fact)), self._text(getattr(valid, fact))
            if (current or "").casefold() != (new or "").casefold():
                changes.append(ZtpFactChange(field=fact, current=current, reported=new))
        action = ZtpApprovalAction.update if changes else ZtpApprovalAction.unchanged
        return self._proposal(action, asset_id=asset.id, asset=self._proposed(valid), changes=changes)

    def _blocked(self, *reasons: str, asset_id: int | None = None) -> ZtpApprovalProposal:
        return self._proposal(ZtpApprovalAction.blocked, asset_id=asset_id, blocked_by=list(reasons))

    @staticmethod
    def _proposal(action, asset_id=None, asset=None, changes=(), blocked_by=()) -> ZtpApprovalProposal:
        body = {
            "action": action,
            "asset_id": asset_id,
            "asset": asset.model_dump() if asset is not None else None,
            "changes": [c.model_dump() for c in changes],
            "blocked_by": list(blocked_by),
        }
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:16]
        return ZtpApprovalProposal(**body, hash=digest)

    @classmethod
    def _proposed(cls, valid: AssetSchema) -> ZtpProposedAsset:
        return ZtpProposedAsset(**{k: cls._text(v) for k, v in valid.model_dump().items()})

    @staticmethod
    def _enum(enum, value: str | None):
        try:
            return enum(value.casefold()) if value else None
        except ValueError:
            return None

    @staticmethod
    def _text(value) -> str | None:
        return None if value is None else str(value)

    @staticmethod
    def _messages(exc: ValidationError) -> list[str]:
        return [f"{'.'.join(str(p) for p in e['loc']) or 'asset'}: {e['msg']}" for e in exc.errors()]
