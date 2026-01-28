from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Literal, ClassVar, Union, Any
from typing import Any

class aaaBaseClass(BaseModel):
    name: str = None

class aaaTacacs(BaseModel):
    port: int = 49
    secret_key: str = None
    secret_key_hashed: str = None
    source_address: str = None # should be reference

class aaaRadius(BaseModel):
    auth_port: int = 1812
    acct_port: int = 1813
    secret_key: str = None
    secret_key_hashed: str = None
    source_address: str = None # should be reference
    retransmit_attempts: int = 3

class aaaServerGroups(aaaBaseClass):
    enable: bool = False
    type: str = 'tacacs_group'  # Only tacacs_group supported
    servers: list = None
    address: str = None
    timeout: int = 30
    tacacs: aaaTacacs = aaaTacacs()
    radius: aaaRadius = aaaRadius()

# Authentication Models
class aaaAuthenticationMethods(BaseModel):
    method: list = None # Ex. ['TACACS_GROUP','LOCAL']

class authenticationUser(BaseModel):
    username: str = None
    password: str = None
    password_hahsed: str = None
    ssh_key: str = None
    role: str = None

class aaaAuthenticationUsers(BaseModel):
    username: authenticationUser = authenticationUser()

class adminUser(BaseModel):
    admin_password: str = None
    admin_password_hashed: str = None

class aaaAuthenticationAdminUsers(BaseModel):
    config: adminUser = adminUser()

class aaaAuthentication(aaaBaseClass):
    config: aaaAuthenticationMethods = aaaAuthenticationMethods()
    admin_user: aaaAuthenticationAdminUsers = aaaAuthenticationAdminUsers()
    users: aaaAuthenticationUsers = aaaAuthenticationUsers()

# Authorization Models
class aaaAuthorizationMethods(BaseModel):
    method: list = None # Ex. ['TACACS_GROUP','LOCAL']

class aaaAuthorizationEvent(BaseModel):
    event_type: dict = {
        'event-type':'command',
        'method':['tacacs_group']
    }

class aaaAuthorizationEvents(BaseModel):
    event: aaaAuthorizationEvent = aaaAuthorizationEvent() 

class aaaAuthorization(aaaBaseClass):
    config: aaaAuthorizationMethods = aaaAuthorizationMethods()
    events: aaaAuthorizationEvents = aaaAuthorizationEvents()

# Accounting Models
class aaaAccountingMethods(BaseModel):
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

class aaaAccounting(aaaBaseClass):
    config: aaaAccountingMethods = aaaAccountingMethods()
    events: aaaAccountingEvents = aaaAccountingEvents()

class aaa(BaseModel):
    config: dict = Field(default_factory=dict)
    server_groups: aaaServerGroups = aaaServerGroups()
    authentication: aaaAuthentication = aaaAuthentication()
    authorization: aaaAuthorization = aaaAuthorization()
    accounting: aaaAccounting = aaaAccounting()
    accounting_events: aaaAccountingEvents = aaaAccountingEvents()