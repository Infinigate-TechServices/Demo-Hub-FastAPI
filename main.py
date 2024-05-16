from fastapi import FastAPI
from pywebio.platform.fastapi import asgi_app
from models import RecordA, TrainingSeat
import cf
import pve
from pywebio_app import pywebio_main

app = FastAPI()

@app.post("/api/v1/dns/remove-record-a")
def remove_record_a(record: RecordA):
    return cf.remove_record_a(record)

@app.post("/api/v1/dns/create-record-a")
def create_record_a(record: RecordA):
    return cf.create_record_a(record)

@app.get("/api/v1/dns/list-seats")
def list_seats():
    return cf.list_seats()

@app.post("/api/v1/pve/create-training-seat")
def create_training_seat(seat: TrainingSeat, template_id: int):
    return pve.create_training_seat(seat, template_id)

@app.post("/api/v1/pve/remove-training-seat")
def remove_training_seat(seat: TrainingSeat):
    return pve.remove_training_seat(seat)

@app.get("/api/v1/pve/list-vms")
def list_vms():
    return pve.list_vms()

# Mounting PyWebIO app
app.mount("/", asgi_app(pywebio_main), name="pywebio")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)