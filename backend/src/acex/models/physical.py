from enum import Enum
from typing import Optional
from datetime import date, datetime
from sqlalchemy import Column, Integer, ForeignKey, Text, UniqueConstraint
from sqlmodel import SQLModel, Field


class PanelType(str, Enum):
    patch = "patch"
    mpo = "mpo"
    splice = "splice"
    odf = "odf"


class ConnectorType(str, Enum):
    lc = "lc"
    sc = "sc"
    mpo12 = "mpo12"
    mpo24 = "mpo24"


class FiberMode(str, Enum):
    sm = "sm"
    mm_om3 = "mm_om3"
    mm_om4 = "mm_om4"


class PortPolarity(str, Enum):
    a = "a"
    b = "b"
    none = "none"


class PortStatus(str, Enum):
    active = "active"
    reserve = "reserve"
    disabled = "disabled"


class FiberType(str, Enum):
    os2 = "os2"
    om3 = "om3"
    om4 = "om4"


class FiberStatus(str, Enum):
    active = "active"
    reserve = "reserve"
    broken = "broken"


class TerminationEnd(str, Enum):
    a = "a"
    b = "b"


TIA_598_COLORS = [
    "blue", "orange", "green", "brown", "slate",
    "white", "red", "black", "yellow", "violet",
    "rose", "aqua",
]


# ── Building ──────────────────────────────────────────────────────


class BuildingBase(SQLModel):
    site_id: int = Field(foreign_key="site.id")
    name: str
    description: Optional[str] = Field(default=None)
    pos_x: Optional[float] = Field(default=None)
    pos_y: Optional[float] = Field(default=None)
    width: float = Field(default=600)
    height: float = Field(default=400)


class Building(BuildingBase, table=True):
    __tablename__ = "phys_building"
    id: Optional[int] = Field(default=None, primary_key=True)


class BuildingResponse(BuildingBase):
    id: int


class BuildingCreate(SQLModel):
    site_id: int
    name: str
    description: Optional[str] = None
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    width: float = 600
    height: float = 400


class BuildingUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


# ── Room ──────────────────────────────────────────────────────────


class RoomBase(SQLModel):
    site_id: int = Field(foreign_key="site.id")
    building_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("phys_building.id"), nullable=True),
    )
    name: str
    floor: int = Field(default=0)
    description: Optional[str] = Field(default=None)
    pos_x: Optional[float] = Field(default=None)
    pos_y: Optional[float] = Field(default=None)


class Room(RoomBase, table=True):
    __tablename__ = "physical_room"
    id: Optional[int] = Field(default=None, primary_key=True)


class RoomResponse(RoomBase):
    id: int


class RoomCreate(SQLModel):
    site_id: int
    building_id: Optional[int] = None
    name: str
    floor: int = 0
    description: Optional[str] = None
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None


class RoomUpdate(SQLModel):
    name: Optional[str] = None
    building_id: Optional[int] = None
    floor: Optional[int] = None
    description: Optional[str] = None
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None


# ── Rack ──────────────────────────────────────────────────────────


class RackBase(SQLModel):
    room_id: int = Field(foreign_key="physical_room.id")
    name: str
    height_u: int = Field(default=42)
    row: Optional[str] = Field(default=None)
    position: Optional[int] = Field(default=None)
    description: Optional[str] = Field(default=None)


class Rack(RackBase, table=True):
    __tablename__ = "physical_rack"
    id: Optional[int] = Field(default=None, primary_key=True)


class RackResponse(RackBase):
    id: int


class RackCreate(SQLModel):
    room_id: int
    name: str
    height_u: int = 42
    row: Optional[str] = None
    position: Optional[int] = None
    description: Optional[str] = None


class RackUpdate(SQLModel):
    name: Optional[str] = None
    height_u: Optional[int] = None
    row: Optional[str] = None
    position: Optional[int] = None
    description: Optional[str] = None


# ── PhysPanel ─────────────────────────────────────────────────────


class PhysPanelBase(SQLModel):
    rack_id: int = Field(foreign_key="physical_rack.id")
    name: str
    panel_type: PanelType
    connector_type: ConnectorType
    fiber_mode: FiberMode
    port_count: int
    rack_unit: int = Field(default=1)
    rack_unit_height: int = Field(default=1)


class PhysPanel(PhysPanelBase, table=True):
    __tablename__ = "phys_panel"
    id: Optional[int] = Field(default=None, primary_key=True)


class PhysPanelResponse(PhysPanelBase):
    id: int


class PhysPanelCreate(SQLModel):
    rack_id: int
    name: str
    panel_type: PanelType
    connector_type: ConnectorType
    fiber_mode: FiberMode
    port_count: int
    rack_unit: int = 1
    rack_unit_height: int = 1


class PhysPanelUpdate(SQLModel):
    name: Optional[str] = None
    panel_type: Optional[PanelType] = None
    connector_type: Optional[ConnectorType] = None
    fiber_mode: Optional[FiberMode] = None
    rack_unit: Optional[int] = None
    rack_unit_height: Optional[int] = None


# ── PhysPanelPort ─────────────────────────────────────────────────


class PhysPanelPortBase(SQLModel):
    panel_id: int = Field(foreign_key="phys_panel.id")
    port_number: int
    label: Optional[str] = Field(default=None)
    polarity: PortPolarity = Field(default=PortPolarity.none)
    status: PortStatus = Field(default=PortStatus.active)


class PhysPanelPort(PhysPanelPortBase, table=True):
    __tablename__ = "phys_panel_port"
    id: Optional[int] = Field(default=None, primary_key=True)


class PhysPanelPortResponse(PhysPanelPortBase):
    id: int


class PhysPanelPortUpdate(SQLModel):
    label: Optional[str] = None
    polarity: Optional[PortPolarity] = None
    status: Optional[PortStatus] = None


# ── PhysFiberTrunk ────────────────────────────────────────────────
# A physical cable. No panel references — terminations are tracked per fiber.


class PhysFiberTrunkBase(SQLModel):
    site_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("site.id"), nullable=True),
    )
    name: str
    fiber_count: int
    fiber_type: FiberType
    connector_type: Optional[ConnectorType] = Field(default=None)
    length_m: Optional[float] = Field(default=None)
    route_description: Optional[str] = Field(default=None)
    installed_at: Optional[date] = Field(default=None)


class PhysFiberTrunk(PhysFiberTrunkBase, table=True):
    __tablename__ = "phys_fiber_trunk"
    id: Optional[int] = Field(default=None, primary_key=True)


class PhysFiberTrunkResponse(PhysFiberTrunkBase):
    id: int


class PhysFiberTrunkCreate(SQLModel):
    site_id: Optional[int] = None
    name: str
    fiber_count: int
    fiber_type: FiberType
    connector_type: Optional[ConnectorType] = None
    length_m: Optional[float] = None
    route_description: Optional[str] = None
    installed_at: Optional[date] = None


class PhysFiberTrunkUpdate(SQLModel):
    name: Optional[str] = None
    fiber_type: Optional[FiberType] = None
    connector_type: Optional[ConnectorType] = None
    length_m: Optional[float] = None
    route_description: Optional[str] = None
    installed_at: Optional[date] = None


# ── PhysFiber ─────────────────────────────────────────────────────


class PhysFiberBase(SQLModel):
    trunk_id: int = Field(foreign_key="phys_fiber_trunk.id")
    fiber_number: int
    color: str
    attenuation_db: Optional[float] = Field(default=None)
    status: FiberStatus = Field(default=FiberStatus.active)


class PhysFiber(PhysFiberBase, table=True):
    __tablename__ = "phys_fiber"
    id: Optional[int] = Field(default=None, primary_key=True)


class PhysFiberResponse(PhysFiberBase):
    id: int


class PhysFiberUpdate(SQLModel):
    attenuation_db: Optional[float] = None
    status: Optional[FiberStatus] = None


# ── PhysFiberTermination ──────────────────────────────────────────
# Where one end ('a' or 'b') of a specific fiber is terminated.
# panel_port_id is null if the fiber end is unterminated (spare, coiled).


class PhysFiberTermination(SQLModel, table=True):
    __tablename__ = "phys_fiber_termination"
    __table_args__ = (UniqueConstraint("fiber_id", "end", name="uq_fiber_end"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    fiber_id: int = Field(
        sa_column=Column(Integer, ForeignKey("phys_fiber.id"), nullable=False)
    )
    end: TerminationEnd
    panel_port_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("phys_panel_port.id"), nullable=True),
    )
    notes: Optional[str] = Field(default=None)


class PhysFiberTerminationCreate(SQLModel):
    fiber_id: int
    end: TerminationEnd
    panel_port_id: Optional[int] = None
    notes: Optional[str] = None


class PhysFiberTerminationResponse(SQLModel):
    id: int
    fiber_id: int
    end: TerminationEnd
    panel_port_id: Optional[int] = None
    notes: Optional[str] = None


class BulkTerminationCreate(SQLModel):
    """Terminate a sequential range of fibers to a sequential range of ports in one shot."""
    trunk_id: int
    end: TerminationEnd
    panel_id: int
    start_fiber: int = 1   # fiber_number to start from
    start_port: int = 1    # port_number to start from
    count: int             # how many fiber/port pairs to create


# ── PhysCrossConnection ───────────────────────────────────────────


class PhysCrossConnectionBase(SQLModel):
    label: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)


class PhysCrossConnection(PhysCrossConnectionBase, table=True):
    __tablename__ = "phys_cross_connection"
    id: Optional[int] = Field(default=None, primary_key=True)
    port_from_id: int = Field(
        sa_column=Column(Integer, ForeignKey("phys_panel_port.id"), nullable=False)
    )
    port_to_id: int = Field(
        sa_column=Column(Integer, ForeignKey("phys_panel_port.id"), nullable=False)
    )
    fiber_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("phys_fiber.id"), nullable=True),
    )
    pair_cc_id: Optional[int] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PhysCrossConnectionResponse(PhysCrossConnectionBase):
    id: int
    port_from_id: int
    port_to_id: int
    fiber_id: Optional[int] = None
    pair_cc_id: Optional[int] = None
    created_at: datetime


class PhysCrossConnectionCreate(SQLModel):
    port_from_id: int
    port_to_id: int
    fiber_id: Optional[int] = None
    label: Optional[str] = None
    description: Optional[str] = None


class PatchCreate(SQLModel):
    """Creates one CC (simplex/BiDi) or two linked CCs (duplex pair)."""
    port_from_id: int
    port_to_id: int
    fiber_id: Optional[int] = None
    label: Optional[str] = None
    duplex: bool = True
    pair_port_from_id: Optional[int] = None
    pair_port_to_id: Optional[int] = None
    pair_fiber_id: Optional[int] = None
    pair_label: Optional[str] = None


# ── PhysSiteLayout ────────────────────────────────────────────────


class PhysSiteLayout(SQLModel, table=True):
    __tablename__ = "phys_site_layout"
    id: Optional[int] = Field(default=None, primary_key=True)
    site_id: int = Field(
        sa_column=Column(Integer, ForeignKey("site.id"), unique=True, nullable=False)
    )
    image_data: str = Field(sa_column=Column(Text, nullable=False))
    image_width: Optional[int] = Field(default=None)
    image_height: Optional[int] = Field(default=None)


class PhysSiteLayoutCreate(SQLModel):
    image_data: str
    image_width: Optional[int] = None
    image_height: Optional[int] = None


class PhysSiteLayoutResponse(SQLModel):
    site_id: int
    image_width: Optional[int] = None
    image_height: Optional[int] = None
