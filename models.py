from pydantic import BaseModel
from typing import List, Optional

class RecordA(BaseModel):
    domain: Optional[str] = None
    ip: Optional[str] = None
    id: str = None

class TrainingSeat(BaseModel):
    name: str

class VM(BaseModel):
    name: str
    template_id: Optional[int]

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
    groupId: int

class CreateUserRequest(BaseModel):
    user: CreateUserInput