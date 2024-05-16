from pydantic import BaseModel

class RecordA(BaseModel):
    domain: str
    ip: str
    id: str = None

class TrainingSeat(BaseModel):
    name: str