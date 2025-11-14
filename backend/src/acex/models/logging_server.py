from sqlmodel import SQLModel, Field
from typing import Any

class LoggingServerBase(SQLModel): ...
    #name: str = None
    
class RemoteServers(LoggingServerBase):
    name: str = None
    host: str = None
    port: int = 514
    transfer: str = 'udp'
    source_address: str = None

class ConsoleLines(LoggingServerBase):
    name: str = None
    line_number: int = None
    logging_synchronous: bool = True

class VtyLines(LoggingServerBase):
    name: str = None
    line_number: int = None
    logging_synchronous: bool = True

class GlobalConfig(LoggingServerBase):
    name: str = None
    buffer_size: int = 4096

class FileConfig(LoggingServerBase):
    name: str = None # object name
    filename: str = None # name of the file
    rotate: int = None # How many versions to keep
    max_size: int = None # Think Ciscos "logging buffered"
    facility: str = None # Level for logs