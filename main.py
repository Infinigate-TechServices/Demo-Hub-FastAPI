from fastapi import FastAPI, HTTPException
from pywebio.platform.fastapi import asgi_app
from models import RecordA, TrainingSeat, ProxyHost, VM
import cf
import pve
import guacamole
from nginx_proxy_manager import list_proxy_hosts, create_proxy_host, remove_proxy_host
from pywebio_app import pywebio_main
import logging

logging.basicConfig(level=logging.INFO)
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
def create_training_seat(vm: VM):
    return pve.create_training_seat(vm.name, vm.template_id)

@app.post("/api/v1/pve/remove-training-seat")
def remove_training_seat(seat: TrainingSeat):
    return pve.remove_training_seat(seat)

@app.post("/api/v1/pve/remove-vm")
def remove_vm(vm: VM):
    return pve.remove_vm(vm.name)

@app.get("/api/v1/pve/list-vms")
def list_vms():
    return pve.list_vms()

@app.get("/api/v1/pve/find-seat-ip/{vm_name}")
async def get_seat_ip(vm_name: str):
    ip_address = pve.find_seat_ip(vm_name)
    if ip_address:
        return {"vm_name": vm_name, "ip_address": ip_address}
    else:
        raise HTTPException(status_code=404, detail="VM not found or IP not configured")

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

# Guacamole endpoints
@app.post("/api/v1/guacamole/users/{username}")
async def create_guacamole_user(username: str):
    logging.info(f"Attempting to create user: {username}")
    success = guacamole.create_user(username)
    if success:
        logging.info(f"User {username} created successfully")
        return {"message": f"User {username} created successfully"}
    else:
        logging.error(f"Failed to create user: {username}")
        raise HTTPException(status_code=500, detail="Failed to create user")

@app.delete("/api/v1/guacamole/users/{username}")
async def remove_guacamole_user(username: str):
    success = guacamole.remove_user(username)
    if success:
        return {"message": f"User {username} removed successfully"}
    else:
        raise HTTPException(status_code=404, detail="User not found or failed to remove")

@app.get("/api/v1/guacamole/users")
async def list_guacamole_users():
    users = guacamole.list_users()
    if users is not None:
        return users
    else:
        raise HTTPException(status_code=500, detail="Failed to retrieve users")

# Mounting PyWebIO app
app.mount("/", asgi_app(pywebio_main), name="pywebio")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)