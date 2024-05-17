from pydantic import BaseModel
from typing import Optional, List

class RecordA(BaseModel):
    domain: Optional[str] = None
    ip: Optional[str] = None
    id: Optional[str] = None

class TrainingSeat(BaseModel):
    name: str

class ProxyHost(BaseModel):
    domain_names: List[str]
    forward_host: str
    forward_port: int
    access_list_id: int = 0
    certificate_id: int = 0
    ssl_forced: int = 0
    caching_enabled: int = 0
    block_exploits: int = 0
    advanced_config: str = ""
    allow_websocket_upgrade: int = 0
    http2_support: int = 0
    forward_scheme: str = "http"
    enabled: int = 1
    locations: List[str] = []
    hsts_enabled: int = 0
    hsts_subdomains: int = 0
    use_default_location: bool = True
    ipv6: bool = True