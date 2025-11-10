from sqlmodel import SQLModel, Field
from typing import Any

class aaaBaseClass(SQLModel):
    name: str = None
    enable: bool = False
    
class aaaServerGroups(aaaBaseClass):
    tacacs_servers: list = None
    tacacs_all: dict = {
        'name':'tacacs_vip',
        'timeout':30,
        'port':49
    }

class aaaAuthentication(aaaBaseClass):
    method: list = None # Ex. ['TACACS_GROUP','LOCAL']

class aaaAuthorizaion(aaaBaseClass):
    method: list = None # Ex. ['TACACS_GROUP','LOCAL']

class aaaAccounting(aaaBaseClass):
    method: list = None # Ex. ['TACACS_GROUP','LOCAL']

class aaaAccountingEvents(aaaBaseClass):
    event: list = [
        {
        'event-type': 'command',
        'config': {
            'event-type': 'command',
            'method': ['tacacs_group']
            }
        },
        {
        'event-type': 'system',
        'config': {
            'event-type': 'system',
            'method': ['tacacs_group']
            }
        }
    ]