from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class RecordA(BaseModel):
    domain: Optional[str] = None
    ip: Optional[str] = None
    id: str = None

class TrainingSeat(BaseModel):
    name: str

class VM(BaseModel):
    name: str
    template_id: Optional[int] = None
    
# Nginx Proxy Manager Models

class ProxyHostCreate(BaseModel):
    domain_names: List[str]
    forward_scheme: str
    forward_host: str
    forward_port: int
    access_list_id: int = 0
    certificate_id: int
    ssl_forced: int = 1
    caching_enabled: int = 0
    block_exploits: int = 1
    advanced_config: str = ""
    allow_websocket_upgrade: int = 1
    http2_support: int = 1
    hsts_enabled: int = 0
    hsts_subdomains: int = 0
    enabled: int = 1
    locations: List[dict] = []
    meta: Optional[dict] = None

class ProxyHost(BaseModel):
    domain_names: List[str]
    forward_host: str
    forward_port: int
    access_list_id: Optional[int] = None
    certificate_id: Optional[int] = None
    ssl_forced: Optional[bool] = False
    caching_enabled: Optional[bool] = False
    block_exploits: Optional[bool] = False
    advanced_config: Optional[str] = ""
    allow_websocket_upgrade: Optional[bool] = False
    http2_support: Optional[bool] = False
    forward_scheme: str = "http"
    enabled: Optional[bool] = True
    hsts_enabled: Optional[bool] = False
    hsts_subdomains: Optional[bool] = False
    meta: Optional[dict] = None  # Optional additional metadata
    locations: Optional[List[dict]] = None  # Optional locations config
    created_on: Optional[str] = None
    modified_on: Optional[str] = None

class CreateUserInput(BaseModel):
    id: str
    email: str
    displayName: str
    firstName: str
    lastName: str
    #groupId: int

class CreateUserRequest(BaseModel):
    user: CreateUserInput
    
class AddTagsRequest(BaseModel):
    vm_name: str
    tags: List[str]
    
class LinkedClone(BaseModel):
    name: str
    template_id: int
    node: str
    
class AddUserToGroupInput(BaseModel):
    userId: str
    groupId: int
    
class GuacamoleConnectionRequest(BaseModel):
    parentIdentifier: str
    name: str
    protocol: str
    parameters: Dict[str, str]
    attributes: Dict[str, Any]

class AddConnectionToUserRequest(BaseModel):
    username: str
    connection_id: str
    
class AddUserToConnectionGroupRequest(BaseModel):
    username: str
    connection_group_id: str

class ConnectionGroupCreate(BaseModel):
    name: str
    parent_identifier: str = "ROOT"
    type: str = "ORGANIZATIONAL"

# Authentik models
class CreateAuthentikUserInput(BaseModel):
    username: str
    email: str
    name: str
    password: str

class AddAuthentikUserToGroupInput(BaseModel):
    user_id: int
    group_id: str
    
    
# FortiGate models
class DHCPReservationRequest(BaseModel):
    mac: str
    seat: str
    dhcp_server_id: int

class DHCPRemovalRequest(BaseModel):
    seat_macs: List[str]
    dhcp_server_id: int
    
class DHCPReservationKnownIPRequest(BaseModel):
    mac: str
    seat: str
    ip: str
    dhcp_server_id: int
