from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class ZtpDhcpScopeRow(SQLModel, table=True):
    """An IPv4 network the ZTP DHCP server hands out addresses in. Addresses are stored as strings."""

    __tablename__ = "ztp_dhcp_scope"

    id: int | None = Field(default=None, primary_key=True)
    network: str = Field(unique=True)
    pool_start: str
    pool_end: str
    gateway: str
    dns_servers: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    domain_name: str | None = None
    description: str | None = None
    updated_by: str | None = None
    updated_at: datetime | None = None


__all__ = ["ZtpDhcpScopeRow"]
