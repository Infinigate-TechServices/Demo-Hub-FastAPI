from fastapi import FastAPI
from pywebio.platform.fastapi import asgi_app
from models import RecordA, TrainingSeat, ProxyHost
import cf
import pve
from nginx_proxy_manager import list_proxy_hosts create_proxy_host remove_proxy_host
from pywebio_app import pywebio_main

app = FastAPI()

# Cloudflare endpoints
@app.post("/api/v1/dns/remove-record-a")
def remove_record_a(record: RecordA):
    return cf.remove_record_a(record)

@app.post("/api/v1/dns/create-record-a")
def create_record_a(record: RecordA):
    return cf.create_record_a(record)

@app.get("/api/v1/dns/list-seats")
def list_seats():
    return cf.list_seats()

# PVE endpoints
@app.post("/api/v1/pve/create-training-seat")
def create_training_seat(seat: TrainingSeat, template_id: int):
    return pve.create_training_seat(seat, template_id)

@app.post("/api/v1/pve/remove-training-seat")
def remove_training_seat(seat: TrainingSeat):
    return pve.remove_training_seat(seat)

@app.get("/api/v1/pve/list-vms")
def list_vms():
    return pve.list_vms()

# Nginx Proxy Manager endpoints
@app.post("/api/v1/nginx/create-proxy-host")
def create_proxy(proxy_host: ProxyHost):
    return create_proxy_host(proxy_host)

@app.delete("/api/v1/nginx/remove-proxy-host/{proxy_host_id}")
def delete_proxy(proxy_host_id: int):
    return remove_proxy_host(proxy_host_id)

@app.get("/api/v1/nginx/list-proxy-hosts")
def get_proxy_hosts():
    return list_proxy_hosts()

# Mounting PyWebIO app
app.mount("/", asgi_app(pywebio_main), name="pywebio")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)