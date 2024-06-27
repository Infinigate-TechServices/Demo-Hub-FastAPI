from fastapi import FastAPI, HTTPException
from pywebio.platform.fastapi import asgi_app
from models import RecordA, TrainingSeat, ProxyHost, VM, CreateUserInput, CreateUserRequest, AddTagsRequest, LinkedClone, AddUserToGroupInput, GuacamoleConnectionRequest, AddConnectionToUserRequest, AddUserToConnectionGroupRequest
import cf
import pve
import guacamole
import lldap
from nginx_proxy_manager import list_proxy_hosts, create_proxy_host, remove_proxy_host
from pywebio_app import pywebio_main
import logging
import traceback

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    return pve.remove_vm(vm)

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
    
@app.get("/api/v1/pve/find-seat-ip-pve/{vm_name}")
async def get_seat_ip_pve(vm_name: str):
    ip_address = pve.find_seat_ip_pve(vm_name)
    if ip_address:
        return {"vm_name": vm_name, "ip_address": ip_address}
    else:
        raise HTTPException(status_code=404, detail="VM not found or IP not configured")

@app.post("/api/v1/pve/add-tags-to-vm")
async def add_tags_to_vm_endpoint(request: AddTagsRequest):
    logger.debug(f"Received request to add tags: {request.dict()}")
    try:
        result = pve.add_tags_to_vm(request)
        if result:
            return {"message": f"Tags added successfully to VM {request.vm_name}"}
        else:
            raise HTTPException(status_code=400, detail="Failed to add tags to VM")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/pve/create-linked-clone")
def create_vm_from_template(vm: LinkedClone):
    return pve.create_linked_clone(vm.name, vm.template_id)

@app.post("/api/v1/pve/start-vm/{vm_name}")
def start_vm(vm_name: str):
    result = pve.start_vm(vm_name)
    print(result)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/v1/pve/run-check-now")
async def run_pve_check_now():
    pve.run_check_now()
    return {"message": "PVE check initiated"}

@app.get("/api/v1/pve/scheduled-deletions")
async def get_scheduled_deletions():
    with pve.deletion_lock:
        scheduled = {vm_name: {'id': info['id'], 'deletion_time': info['deletion_time'].isoformat()} 
                     for vm_name, info in pve.vms_scheduled_for_deletion.items()}
    return {"scheduled_deletions": scheduled}

@app.post("/api/v1/pve/shutdown-vm/{vm_name}")
def shutdown_vm(vm_name: str):
    return pve.shutdown_vm(vm_name)

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
    
@app.post("/api/v1/guacamole/connections")
async def create_guacamole_connection(request: GuacamoleConnectionRequest):
    try:
        result = guacamole.create_rdp_connection(
            connection_name=request.connection_name,
            hostname=request.hostname,
            port=request.port,
            username=request.username,
            password=request.password,
            domain=request.domain,
            security=request.security,
            ignore_cert=request.ignore_cert,
            enable_font_smoothing=request.enable_font_smoothing,
            server_layout=request.server_layout,
            guacd_hostname=request.guacd_hostname,
            guacd_port=request.guacd_port
        )
        if result:
            return {"message": "Connection created successfully", "connection_id": result.get("identifier")}
        else:
            raise HTTPException(status_code=500, detail="Failed to create connection")
    except Exception as e:
        logger.error(f"Error creating connection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create connection: {str(e)}")
    
@app.post("/api/v1/guacamole/add-to-connection")
async def add_connection_to_user_endpoint(request: AddConnectionToUserRequest):
    result = guacamole.add_connection_to_user(request.username, request.connection_id)
    if isinstance(result, tuple) and not result[0]:
        raise HTTPException(status_code=500, detail=f"Failed to add connection to user: {result[1]}")
    elif result:
        return {"message": f"Connection {request.connection_id} added to user {request.username} successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to add connection to user")

@app.get("/api/v1/guacamole/get-connection-id/{connection_name}")
async def get_connection_id_endpoint(connection_name: str):
    connection_name = connection_name.replace("%20", " ")
    connection_id = guacamole.get_connection_id(connection_name)
    if connection_id:
        return {"connection_name": connection_name, "connection_id": connection_id}
    else:
        raise HTTPException(status_code=404, detail=f"No connection found with name: {connection_name}")

@app.post("/api/v2/guacamole/connections")
async def create_guacamole_connection_v2(request: GuacamoleConnectionRequest):
    logger.info(f"Received connection request: {request}")
    try:
        result = guacamole.create_connection(request.dict())
        if result and 'identifier' in result:
            return {"message": "Connection created successfully", "connection_id": result['identifier']}
        else:
            raise HTTPException(status_code=500, detail="Failed to create connection")
    except Exception as e:
        logger.error(f"Error creating connection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create connection: {str(e)}")

@app.post("/api/v2/guacamole/add-to-connection")
async def add_connection_to_user_v2(request: AddConnectionToUserRequest):
    result = guacamole.add_connection_to_user(request.username, request.connection_id)
    if result:
        return {"message": f"Connection {request.connection_id} added to user {request.username} successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to add connection to user")

@app.post("/api/v2/guacamole/add-to-connection-group")
async def add_user_to_connection_group_v2(request: AddUserToConnectionGroupRequest):
    result = guacamole.add_user_to_connection_group(request.username, request.connection_group_id)
    if result:
        return {"message": f"User {request.username} added to connection group {request.connection_group_id} successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to add user to connection group")

# LLDAP endpoints
@app.post("/api/v1/lldap/users")
async def create_lldap_user(user: CreateUserInput):
    try:
        created_user = lldap.create_user(
            id=user.id,
            email=user.email,
            displayName=user.displayName,
            firstName=user.firstName,
            lastName=user.lastName
        )
        return {"message": f"User {user.id} created successfully", "user": created_user}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/v1/lldap/users")
async def list_lldap_users():
    users = lldap.list_users()
    return {"users": users}

@app.delete("/api/v1/lldap/users/{user_id}")
async def delete_lldap_user(user_id: str):
    success = lldap.remove_user(user_id)
    if success:
        return {"message": f"User {user_id} deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="User not found or failed to delete")
    
@app.get("/api/v1/lldap/groups")
async def list_lldap_groups():
    try:
        groups = lldap.list_groups()
        return {"groups": groups}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.post("/api/v1/lldap/add-user-to-group")
async def add_user_to_group(input: AddUserToGroupInput):
    try:
        group_added = lldap.add_user_to_group(input.userId, input.groupId)
        if group_added:
            return {"message": f"User {input.userId} added to group {input.groupId} successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to add user to group")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Mounting PyWebIO app
app.mount("/", asgi_app(pywebio_main), name="pywebio")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)