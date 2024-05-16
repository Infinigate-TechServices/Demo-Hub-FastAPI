from pydantic import BaseModel
from typing import Optional

class RecordA(BaseModel):
    domain: Optional[str] = None
    ip: Optional[str] = None
    id: Optional[str] = None

class TrainingSeat(BaseModel):
    name: str