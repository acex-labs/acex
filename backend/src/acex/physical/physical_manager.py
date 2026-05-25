from sqlmodel import Session, select
from sqlalchemy import or_, delete as sql_delete
from fastapi import HTTPException

from acex.models.physical import (
    Building, BuildingCreate, BuildingUpdate, BuildingResponse,
    Room, RoomCreate, RoomUpdate, RoomResponse,
    Rack, RackCreate, RackUpdate, RackResponse,
    PhysPanel, PhysPanelCreate, PhysPanelResponse,
    PhysPanelPort, PhysPanelPortUpdate, PhysPanelPortResponse,
    PhysFiberTrunk, PhysFiberTrunkCreate, PhysFiberTrunkResponse,
    PhysFiber, PhysFiberResponse,
    PhysFiberTermination, PhysFiberTerminationCreate, PhysFiberTerminationResponse,
    BulkTerminationCreate,
    PhysCrossConnection, PhysCrossConnectionCreate, PhysCrossConnectionResponse,
    PatchCreate,
    PhysSiteLayout, PhysSiteLayoutCreate, PhysSiteLayoutResponse,
    TIA_598_COLORS,
)


class PhysicalManager:
    def __init__(self, db):
        self.db = db

    def _session(self):
        return Session(self.db.connection.engine)

    # ── Buildings ─────────────────────────────────────────────────

    def create_building(self, building: BuildingCreate) -> BuildingResponse:
        with self._session() as session:
            obj = Building(**building.model_dump())
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return BuildingResponse.model_validate(obj)

    def list_buildings(self, site_id: int) -> list[BuildingResponse]:
        with self._session() as session:
            rows = session.exec(select(Building).where(Building.site_id == site_id)).all()
            return [BuildingResponse.model_validate(b) for b in rows]

    def get_building(self, building_id: int) -> BuildingResponse:
        with self._session() as session:
            obj = session.get(Building, building_id)
            if not obj:
                raise HTTPException(status_code=404, detail="Building not found")
            return BuildingResponse.model_validate(obj)

    def update_building(self, building_id: int, data: BuildingUpdate) -> BuildingResponse:
        with self._session() as session:
            obj = session.get(Building, building_id)
            if not obj:
                raise HTTPException(status_code=404, detail="Building not found")
            for k, v in data.model_dump(exclude_unset=True).items():
                setattr(obj, k, v)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return BuildingResponse.model_validate(obj)

    def delete_building(self, building_id: int):
        with self._session() as session:
            if not session.get(Building, building_id):
                raise HTTPException(status_code=404, detail="Building not found")
            room_ids = session.exec(select(Room.id).where(Room.building_id == building_id)).all()
            for room_id in room_ids:
                rack_ids = session.exec(select(Rack.id).where(Rack.room_id == room_id)).all()
                for rack_id in rack_ids:
                    panel_ids = session.exec(select(PhysPanel.id).where(PhysPanel.rack_id == rack_id)).all()
                    for panel_id in panel_ids:
                        self._cascade_delete_panel(session, panel_id)
                    session.execute(sql_delete(Rack).where(Rack.id == rack_id))
                    session.flush()
                session.execute(sql_delete(Room).where(Room.id == room_id))
                session.flush()
            session.execute(sql_delete(Building).where(Building.id == building_id))
            session.commit()

    # ── Rooms ─────────────────────────────────────────────────────

    def create_room(self, room: RoomCreate) -> RoomResponse:
        with self._session() as session:
            obj = Room(**room.model_dump())
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return RoomResponse.model_validate(obj)

    def list_rooms(self, site_id: int) -> list[RoomResponse]:
        with self._session() as session:
            rows = session.exec(select(Room).where(Room.site_id == site_id)).all()
            return [RoomResponse.model_validate(r) for r in rows]

    def get_room(self, room_id: int) -> RoomResponse:
        with self._session() as session:
            obj = session.get(Room, room_id)
            if not obj:
                raise HTTPException(status_code=404, detail="Room not found")
            return RoomResponse.model_validate(obj)

    def update_room(self, room_id: int, data: RoomUpdate) -> RoomResponse:
        with self._session() as session:
            obj = session.get(Room, room_id)
            if not obj:
                raise HTTPException(status_code=404, detail="Room not found")
            for k, v in data.model_dump(exclude_unset=True).items():
                setattr(obj, k, v)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return RoomResponse.model_validate(obj)

    def delete_room(self, room_id: int):
        with self._session() as session:
            if not session.get(Room, room_id):
                raise HTTPException(status_code=404, detail="Room not found")
            rack_ids = session.exec(select(Rack.id).where(Rack.room_id == room_id)).all()
            for rack_id in rack_ids:
                panel_ids = session.exec(select(PhysPanel.id).where(PhysPanel.rack_id == rack_id)).all()
                for panel_id in panel_ids:
                    self._cascade_delete_panel(session, panel_id)
                session.execute(sql_delete(Rack).where(Rack.id == rack_id))
                session.flush()
            session.execute(sql_delete(Room).where(Room.id == room_id))
            session.commit()

    # ── Racks ─────────────────────────────────────────────────────

    def create_rack(self, rack: RackCreate) -> RackResponse:
        with self._session() as session:
            obj = Rack(**rack.model_dump())
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return RackResponse.model_validate(obj)

    def list_racks(self, room_id: int) -> list[RackResponse]:
        with self._session() as session:
            rows = session.exec(select(Rack).where(Rack.room_id == room_id)).all()
            return [RackResponse.model_validate(r) for r in rows]

    def get_rack(self, rack_id: int) -> RackResponse:
        with self._session() as session:
            obj = session.get(Rack, rack_id)
            if not obj:
                raise HTTPException(status_code=404, detail="Rack not found")
            return RackResponse.model_validate(obj)

    def update_rack(self, rack_id: int, data: RackUpdate) -> RackResponse:
        with self._session() as session:
            obj = session.get(Rack, rack_id)
            if not obj:
                raise HTTPException(status_code=404, detail="Rack not found")
            for k, v in data.model_dump(exclude_unset=True).items():
                setattr(obj, k, v)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return RackResponse.model_validate(obj)

    def delete_rack(self, rack_id: int):
        with self._session() as session:
            if not session.get(Rack, rack_id):
                raise HTTPException(status_code=404, detail="Rack not found")
            panel_ids = session.exec(select(PhysPanel.id).where(PhysPanel.rack_id == rack_id)).all()
            for panel_id in panel_ids:
                self._cascade_delete_panel(session, panel_id)
            session.execute(sql_delete(Rack).where(Rack.id == rack_id))
            session.commit()

    # ── Panels ────────────────────────────────────────────────────

    def create_panel(self, panel: PhysPanelCreate) -> PhysPanelResponse:
        with self._session() as session:
            obj = PhysPanel(**panel.model_dump())
            session.add(obj)
            session.commit()
            session.refresh(obj)
            for i in range(1, panel.port_count + 1):
                session.add(PhysPanelPort(panel_id=obj.id, port_number=i))
            session.commit()
            return PhysPanelResponse.model_validate(obj)

    def list_panels(self, rack_id: int) -> list[PhysPanelResponse]:
        with self._session() as session:
            rows = session.exec(
                select(PhysPanel).where(PhysPanel.rack_id == rack_id)
                .order_by(PhysPanel.rack_unit)
            ).all()
            return [PhysPanelResponse.model_validate(r) for r in rows]

    def get_panel(self, panel_id: int) -> PhysPanelResponse:
        with self._session() as session:
            obj = session.get(PhysPanel, panel_id)
            if not obj:
                raise HTTPException(status_code=404, detail="Panel not found")
            return PhysPanelResponse.model_validate(obj)

    def delete_panel(self, panel_id: int):
        with self._session() as session:
            if not session.get(PhysPanel, panel_id):
                raise HTTPException(status_code=404, detail="Panel not found")
            self._cascade_delete_panel(session, panel_id)
            session.commit()

    def _cascade_delete_panel(self, session, panel_id: int):
        port_ids = session.exec(
            select(PhysPanelPort.id).where(PhysPanelPort.panel_id == panel_id)
        ).all()
        if port_ids:
            # Trunk survives; only the terminations pointing here are removed
            session.execute(
                sql_delete(PhysFiberTermination).where(PhysFiberTermination.panel_port_id.in_(port_ids))
            )
            session.flush()
            session.execute(
                sql_delete(PhysCrossConnection).where(
                    or_(
                        PhysCrossConnection.port_from_id.in_(port_ids),
                        PhysCrossConnection.port_to_id.in_(port_ids),
                    )
                )
            )
            session.flush()
        session.execute(sql_delete(PhysPanelPort).where(PhysPanelPort.panel_id == panel_id))
        session.flush()
        session.execute(sql_delete(PhysPanel).where(PhysPanel.id == panel_id))
        session.flush()

    # ── Panel Ports ───────────────────────────────────────────────

    def list_panel_ports(self, panel_id: int) -> list[PhysPanelPortResponse]:
        with self._session() as session:
            rows = session.exec(
                select(PhysPanelPort).where(PhysPanelPort.panel_id == panel_id)
                .order_by(PhysPanelPort.port_number)
            ).all()
            return [PhysPanelPortResponse.model_validate(r) for r in rows]

    def update_panel_port(self, port_id: int, data: PhysPanelPortUpdate) -> PhysPanelPortResponse:
        with self._session() as session:
            obj = session.get(PhysPanelPort, port_id)
            if not obj:
                raise HTTPException(status_code=404, detail="Port not found")
            for k, v in data.model_dump(exclude_unset=True).items():
                setattr(obj, k, v)
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return PhysPanelPortResponse.model_validate(obj)

    # ── Fiber Trunks ──────────────────────────────────────────────

    def create_fiber_trunk(self, trunk: PhysFiberTrunkCreate) -> PhysFiberTrunkResponse:
        with self._session() as session:
            obj = PhysFiberTrunk(**trunk.model_dump())
            session.add(obj)
            session.commit()
            session.refresh(obj)
            for i in range(1, trunk.fiber_count + 1):
                color = TIA_598_COLORS[(i - 1) % len(TIA_598_COLORS)]
                session.add(PhysFiber(trunk_id=obj.id, fiber_number=i, color=color))
            session.commit()
            return PhysFiberTrunkResponse.model_validate(obj)

    def list_fiber_trunks_by_panel(self, panel_id: int) -> list[PhysFiberTrunkResponse]:
        """Trunks that have at least one fiber terminated to a port in this panel."""
        with self._session() as session:
            port_ids = session.exec(
                select(PhysPanelPort.id).where(PhysPanelPort.panel_id == panel_id)
            ).all()
            if not port_ids:
                return []
            fiber_ids = session.exec(
                select(PhysFiberTermination.fiber_id).where(
                    PhysFiberTermination.panel_port_id.in_(port_ids)
                )
            ).all()
            if not fiber_ids:
                return []
            trunk_ids = session.exec(
                select(PhysFiber.trunk_id).where(PhysFiber.id.in_(fiber_ids)).distinct()
            ).all()
            rows = session.exec(
                select(PhysFiberTrunk).where(PhysFiberTrunk.id.in_(trunk_ids))
            ).all()
            return [PhysFiberTrunkResponse.model_validate(r) for r in rows]

    def get_fiber_trunk(self, trunk_id: int) -> PhysFiberTrunkResponse:
        with self._session() as session:
            obj = session.get(PhysFiberTrunk, trunk_id)
            if not obj:
                raise HTTPException(status_code=404, detail="Fiber trunk not found")
            return PhysFiberTrunkResponse.model_validate(obj)

    def delete_fiber_trunk(self, trunk_id: int):
        with self._session() as session:
            if not session.get(PhysFiberTrunk, trunk_id):
                raise HTTPException(status_code=404, detail="Fiber trunk not found")
            self._cascade_delete_trunk(session, trunk_id)
            session.commit()

    def _cascade_delete_trunk(self, session, trunk_id: int):
        fiber_ids = session.exec(
            select(PhysFiber.id).where(PhysFiber.trunk_id == trunk_id)
        ).all()
        if fiber_ids:
            session.execute(
                sql_delete(PhysCrossConnection).where(PhysCrossConnection.fiber_id.in_(fiber_ids))
            )
            session.flush()
            session.execute(
                sql_delete(PhysFiberTermination).where(PhysFiberTermination.fiber_id.in_(fiber_ids))
            )
            session.flush()
        session.execute(sql_delete(PhysFiber).where(PhysFiber.trunk_id == trunk_id))
        session.flush()
        session.execute(sql_delete(PhysFiberTrunk).where(PhysFiberTrunk.id == trunk_id))
        session.flush()

    # ── Fibers ────────────────────────────────────────────────────

    def list_fibers(self, trunk_id: int) -> list[PhysFiberResponse]:
        with self._session() as session:
            rows = session.exec(
                select(PhysFiber).where(PhysFiber.trunk_id == trunk_id)
                .order_by(PhysFiber.fiber_number)
            ).all()
            return [PhysFiberResponse.model_validate(r) for r in rows]

    # ── Fiber Terminations ────────────────────────────────────────

    def create_fiber_termination(self, term: PhysFiberTerminationCreate) -> PhysFiberTerminationResponse:
        with self._session() as session:
            if not session.get(PhysFiber, term.fiber_id):
                raise HTTPException(status_code=404, detail="Fiber not found")
            existing = session.exec(
                select(PhysFiberTermination).where(
                    PhysFiberTermination.fiber_id == term.fiber_id,
                    PhysFiberTermination.end == term.end,
                )
            ).first()
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Fiber {term.fiber_id} end '{term.end}' already has a termination",
                )
            obj = PhysFiberTermination(**term.model_dump())
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return PhysFiberTerminationResponse.model_validate(obj)

    def list_fiber_terminations(self, trunk_id: int) -> list[PhysFiberTerminationResponse]:
        with self._session() as session:
            fiber_ids = session.exec(
                select(PhysFiber.id).where(PhysFiber.trunk_id == trunk_id)
            ).all()
            if not fiber_ids:
                return []
            rows = session.exec(
                select(PhysFiberTermination).where(PhysFiberTermination.fiber_id.in_(fiber_ids))
                .order_by(PhysFiberTermination.fiber_id, PhysFiberTermination.end)
            ).all()
            return [PhysFiberTerminationResponse.model_validate(r) for r in rows]

    def delete_fiber_termination(self, term_id: int):
        with self._session() as session:
            obj = session.get(PhysFiberTermination, term_id)
            if not obj:
                raise HTTPException(status_code=404, detail="Fiber termination not found")
            session.delete(obj)
            session.commit()

    def create_bulk_terminations(self, data: BulkTerminationCreate) -> list[PhysFiberTerminationResponse]:
        with self._session() as session:
            if not session.get(PhysFiberTrunk, data.trunk_id):
                raise HTTPException(status_code=404, detail="Fiber trunk not found")
            if not session.get(PhysPanel, data.panel_id):
                raise HTTPException(status_code=404, detail="Panel not found")

            fibers = session.exec(
                select(PhysFiber)
                .where(PhysFiber.trunk_id == data.trunk_id)
                .where(PhysFiber.fiber_number >= data.start_fiber)
                .order_by(PhysFiber.fiber_number)
                .limit(data.count)
            ).all()

            ports = session.exec(
                select(PhysPanelPort)
                .where(PhysPanelPort.panel_id == data.panel_id)
                .where(PhysPanelPort.port_number >= data.start_port)
                .order_by(PhysPanelPort.port_number)
                .limit(data.count)
            ).all()

            if len(fibers) < data.count:
                raise HTTPException(status_code=400, detail=f"Not enough fibers: need {data.count}, trunk has {len(fibers)} from fiber {data.start_fiber}")
            if len(ports) < data.count:
                raise HTTPException(status_code=400, detail=f"Not enough ports: need {data.count}, panel has {len(ports)} from port {data.start_port}")

            created = []
            for fiber, port in zip(fibers, ports):
                existing = session.exec(
                    select(PhysFiberTermination).where(
                        PhysFiberTermination.fiber_id == fiber.id,
                        PhysFiberTermination.end == data.end,
                    )
                ).first()
                if existing:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Fiber {fiber.fiber_number} end '{data.end}' already has a termination",
                    )
                obj = PhysFiberTermination(fiber_id=fiber.id, end=data.end, panel_port_id=port.id)
                session.add(obj)
                created.append(obj)

            session.commit()
            for obj in created:
                session.refresh(obj)
            return [PhysFiberTerminationResponse.model_validate(obj) for obj in created]

    # ── Cross-connections ─────────────────────────────────────────

    def create_cross_connection(self, cc: PhysCrossConnectionCreate) -> PhysCrossConnectionResponse:
        with self._session() as session:
            obj = PhysCrossConnection(**cc.model_dump())
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return PhysCrossConnectionResponse.model_validate(obj)

    def create_patch(self, patch: PatchCreate) -> list[PhysCrossConnectionResponse]:
        with self._session() as session:
            cc_a = PhysCrossConnection(
                port_from_id=patch.port_from_id,
                port_to_id=patch.port_to_id,
                fiber_id=patch.fiber_id,
                label=patch.label,
            )
            session.add(cc_a)
            session.flush()
            if not patch.duplex:
                session.commit()
                session.refresh(cc_a)
                return [PhysCrossConnectionResponse.model_validate(cc_a)]
            cc_b = PhysCrossConnection(
                port_from_id=patch.pair_port_from_id,
                port_to_id=patch.pair_port_to_id,
                fiber_id=patch.pair_fiber_id,
                label=patch.pair_label,
                pair_cc_id=cc_a.id,
            )
            session.add(cc_b)
            session.flush()
            cc_a.pair_cc_id = cc_b.id
            session.add(cc_a)
            session.commit()
            session.refresh(cc_a)
            session.refresh(cc_b)
            return [
                PhysCrossConnectionResponse.model_validate(cc_a),
                PhysCrossConnectionResponse.model_validate(cc_b),
            ]

    def list_cross_connections_by_panel(self, panel_id: int) -> list[PhysCrossConnectionResponse]:
        with self._session() as session:
            port_ids = session.exec(
                select(PhysPanelPort.id).where(PhysPanelPort.panel_id == panel_id)
            ).all()
            if not port_ids:
                return []
            rows = session.exec(
                select(PhysCrossConnection).where(
                    or_(
                        PhysCrossConnection.port_from_id.in_(port_ids),
                        PhysCrossConnection.port_to_id.in_(port_ids),
                    )
                )
            ).all()
            return [PhysCrossConnectionResponse.model_validate(r) for r in rows]

    def delete_cross_connection(self, cc_id: int):
        with self._session() as session:
            obj = session.get(PhysCrossConnection, cc_id)
            if not obj:
                raise HTTPException(status_code=404, detail="Cross-connection not found")
            session.delete(obj)
            session.commit()

    # ── Trace ─────────────────────────────────────────────────────

    def trace(self, port_id: int) -> dict:
        with self._session() as session:
            port = session.get(PhysPanelPort, port_id)
            if not port:
                raise HTTPException(status_code=404, detail="Port not found")
            cc = session.exec(
                select(PhysCrossConnection).where(
                    or_(
                        PhysCrossConnection.port_from_id == port_id,
                        PhysCrossConnection.port_to_id == port_id,
                    )
                )
            ).first()
            result = {"port": PhysPanelPortResponse.model_validate(port).model_dump()}
            if not cc:
                return result
            other_port_id = cc.port_to_id if cc.port_from_id == port_id else cc.port_from_id
            other_port = session.get(PhysPanelPort, other_port_id)
            fiber = session.get(PhysFiber, cc.fiber_id) if cc.fiber_id else None
            trunk = session.get(PhysFiberTrunk, fiber.trunk_id) if fiber else None
            result["cross_connection"] = PhysCrossConnectionResponse.model_validate(cc).model_dump()
            if fiber:
                result["fiber"] = PhysFiberResponse.model_validate(fiber).model_dump()
            if trunk:
                result["trunk"] = PhysFiberTrunkResponse.model_validate(trunk).model_dump()
            if other_port:
                result["remote_port"] = PhysPanelPortResponse.model_validate(other_port).model_dump()
                remote_panel = session.get(PhysPanel, other_port.panel_id)
                if remote_panel:
                    result["remote_panel"] = PhysPanelResponse.model_validate(remote_panel).model_dump()
            return result

    # ── Site overview ─────────────────────────────────────────────

    def get_site_overview(self, site_id: int) -> dict:
        with self._session() as session:
            buildings = session.exec(select(Building).where(Building.site_id == site_id)).all()
            rooms = session.exec(select(Room).where(Room.site_id == site_id)).all()
            room_ids = [r.id for r in rooms]
            racks = session.exec(select(Rack).where(Rack.room_id.in_(room_ids))).all() if room_ids else []
            rack_ids = [r.id for r in racks]
            panels = session.exec(select(PhysPanel).where(PhysPanel.rack_id.in_(rack_ids))).all() if rack_ids else []
            panel_ids = [p.id for p in panels]

            used_port_counts: dict[int, int] = {}
            if panel_ids:
                all_ports = session.exec(
                    select(PhysPanelPort).where(PhysPanelPort.panel_id.in_(panel_ids))
                ).all()
                port_id_to_panel = {p.id: p.panel_id for p in all_ports}
                all_port_ids = list(port_id_to_panel.keys())
                if all_port_ids:
                    ccs = session.exec(
                        select(PhysCrossConnection).where(
                            or_(
                                PhysCrossConnection.port_from_id.in_(all_port_ids),
                                PhysCrossConnection.port_to_id.in_(all_port_ids),
                            )
                        )
                    ).all()
                    used_ids: set[int] = set()
                    for cc in ccs:
                        if cc.port_from_id in port_id_to_panel:
                            used_ids.add(cc.port_from_id)
                        if cc.port_to_id in port_id_to_panel:
                            used_ids.add(cc.port_to_id)
                    for pid in used_ids:
                        p = port_id_to_panel[pid]
                        used_port_counts[p] = used_port_counts.get(p, 0) + 1

            panel_dicts = []
            for p in panels:
                d = PhysPanelResponse.model_validate(p).model_dump()
                d["used_ports"] = used_port_counts.get(p.id, 0)
                panel_dicts.append(d)

            trunk_connections = self._compute_trunk_connections(session, panel_ids, panels, racks, rooms)
            site_trunks = session.exec(
                select(PhysFiberTrunk).where(PhysFiberTrunk.site_id == site_id)
            ).all()

            return {
                "buildings": [BuildingResponse.model_validate(b).model_dump() for b in buildings],
                "rooms": [RoomResponse.model_validate(r).model_dump() for r in rooms],
                "racks": [RackResponse.model_validate(r).model_dump() for r in racks],
                "panels": panel_dicts,
                "trunks": [PhysFiberTrunkResponse.model_validate(t).model_dump() for t in site_trunks],
                "trunk_connections": trunk_connections,
            }

    def _compute_trunk_connections(self, session, panel_ids, panels, racks, rooms) -> list[dict]:
        if not panel_ids:
            return []
        all_ports = session.exec(
            select(PhysPanelPort).where(PhysPanelPort.panel_id.in_(panel_ids))
        ).all()
        port_ids = [p.id for p in all_ports]
        if not port_ids:
            return []
        terminations = session.exec(
            select(PhysFiberTermination).where(PhysFiberTermination.panel_port_id.in_(port_ids))
        ).all()
        if not terminations:
            return []

        port_to_panel = {p.id: p.panel_id for p in all_ports}
        panel_to_rack = {p.id: p.rack_id for p in panels}
        rack_to_room = {r.id: r.room_id for r in racks}

        def port_room(port_id):
            pid = port_to_panel.get(port_id)
            rid = pid and panel_to_rack.get(pid)
            return rid and rack_to_room.get(rid)

        fiber_ends: dict[int, dict] = {}
        for t in terminations:
            if not t.panel_port_id:
                continue
            room_id = port_room(t.panel_port_id)
            if room_id:
                fiber_ends.setdefault(t.fiber_id, {})[t.end] = room_id

        if not fiber_ends:
            return []

        fiber_ids = list(fiber_ends.keys())
        fibers = session.exec(select(PhysFiber).where(PhysFiber.id.in_(fiber_ids))).all()
        fiber_trunk = {f.id: f.trunk_id for f in fibers}
        trunk_ids = list(set(fiber_trunk.values()))
        trunks = session.exec(select(PhysFiberTrunk).where(PhysFiberTrunk.id.in_(trunk_ids))).all()
        trunk_map = {t.id: t for t in trunks}

        segments: dict[tuple, int] = {}
        for fiber_id, ends in fiber_ends.items():
            room_a = ends.get("a")
            room_b = ends.get("b")
            if not room_a or not room_b or room_a == room_b:
                continue
            trunk_id = fiber_trunk.get(fiber_id)
            if not trunk_id:
                continue
            key = (trunk_id, min(room_a, room_b), max(room_a, room_b))
            segments[key] = segments.get(key, 0) + 1

        result = []
        for (trunk_id, room_a, room_b), count in segments.items():
            t = trunk_map.get(trunk_id)
            if t:
                result.append({
                    "trunk_id": trunk_id,
                    "trunk_name": t.name,
                    "fiber_type": t.fiber_type,
                    "fiber_count": count,
                    "room_a_id": room_a,
                    "room_b_id": room_b,
                })
        return result

    # ── All ports for a site ──────────────────────────────────────

    def list_all_ports_for_site(self, site_id: int) -> list[dict]:
        with self._session() as session:
            rooms = session.exec(select(Room).where(Room.site_id == site_id)).all()
            room_ids = [r.id for r in rooms]
            if not room_ids:
                return []
            racks = session.exec(select(Rack).where(Rack.room_id.in_(room_ids))).all()
            rack_ids = [r.id for r in racks]
            if not rack_ids:
                return []
            panels = session.exec(select(PhysPanel).where(PhysPanel.rack_id.in_(rack_ids))).all()
            panel_ids = [p.id for p in panels]
            if not panel_ids:
                return []
            ports = session.exec(
                select(PhysPanelPort).where(PhysPanelPort.panel_id.in_(panel_ids))
                .order_by(PhysPanelPort.panel_id, PhysPanelPort.port_number)
            ).all()
            panel_map = {p.id: p for p in panels}
            rack_map = {r.id: r for r in racks}
            room_map = {r.id: r for r in rooms}
            result = []
            for port in ports:
                panel = panel_map.get(port.panel_id)
                rack = rack_map.get(panel.rack_id) if panel else None
                room = room_map.get(rack.room_id) if rack else None
                result.append({
                    "id": port.id,
                    "port_number": port.port_number,
                    "label": port.label,
                    "status": port.status,
                    "panel_id": port.panel_id,
                    "panel_name": panel.name if panel else "",
                    "rack_name": rack.name if rack else "",
                    "room_name": room.name if room else "",
                    "display": f"{room.name if room else '?'} / {rack.name if rack else '?'} / {panel.name if panel else '?'} / P{port.port_number}",
                })
            return result

    # ── Site layout ───────────────────────────────────────────────

    def get_site_layout(self, site_id: int) -> dict:
        with self._session() as session:
            layout = session.exec(
                select(PhysSiteLayout).where(PhysSiteLayout.site_id == site_id)
            ).first()
            if not layout:
                raise HTTPException(status_code=404, detail="No layout for this site")
            return {
                "site_id": layout.site_id,
                "image_data": layout.image_data,
                "image_width": layout.image_width,
                "image_height": layout.image_height,
            }

    def set_site_layout(self, site_id: int, data: PhysSiteLayoutCreate) -> dict:
        with self._session() as session:
            existing = session.exec(
                select(PhysSiteLayout).where(PhysSiteLayout.site_id == site_id)
            ).first()
            if existing:
                existing.image_data = data.image_data
                existing.image_width = data.image_width
                existing.image_height = data.image_height
                session.add(existing)
            else:
                session.add(PhysSiteLayout(
                    site_id=site_id,
                    image_data=data.image_data,
                    image_width=data.image_width,
                    image_height=data.image_height,
                ))
            session.commit()
            return {"site_id": site_id, "image_width": data.image_width, "image_height": data.image_height}

    def delete_site_layout(self, site_id: int):
        with self._session() as session:
            existing = session.exec(
                select(PhysSiteLayout).where(PhysSiteLayout.site_id == site_id)
            ).first()
            if existing:
                session.delete(existing)
                session.commit()
