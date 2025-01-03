from fastapi import FastAPI, HTTPException, Query
from pywebio.platform.fastapi import asgi_app
from models import RecordA, TrainingSeat, ProxyHost, ProxyHostCreate, VM, CreateUserInput, CreateUserRequest, AddTagsRequest, LinkedClone, AddUserToGroupInput, GuacamoleConnectionRequest, AddConnectionToUserRequest, AddUserToConnectionGroupRequest, CreateAuthentikUserInput, AddAuthentikUserToGroupInput, DHCPRemovalRequest, DHCPReservationRequest, DHCPReservationKnownIPRequest, ConnectionGroupCreate
import cf
import pve
import guacamole
import lldap
import authentik
import nginx_proxy_manager
import fortigate
from pywebio_app import pywebio_main
import logging
import traceback
from datetime import datetime
import requests
import json

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
@app.get("/api/v1/pve/evaluate-nodes")
async def get_best_node():
    try:
        best_node = pve.evaluate_nodes()
        if best_node:
            return {"best_node": best_node}
        else:
            raise HTTPException(status_code=404, detail="No suitable node found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    
@app.get("/api/v1/pve/evaluate-nodes-for-date/{target_date}")
async def get_best_node_for_date(target_date: str):
    try:
        # Validate the date format
        datetime.strptime(target_date, "%d-%m-%Y")
        
        best_node = pve.evaluate_nodes_for_date(target_date)
        if best_node:
            return {"best_node": best_node, "target_date": target_date}
        else:
            raise HTTPException(status_code=404, detail="No suitable node found for the given date")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Please use DD-MM-YYYY")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/api/v1/pve/create-training-seat")
def create_training_seat(vm: VM):
    return pve.create_training_seat(vm.name, vm.template_id)

@app.post("/api/v1/pve/remove-training-seat")
def remove_training_seat(seat: TrainingSeat):
    return pve.remove_training_seat(seat)

@app.post("/api/v1/pve/remove-vm")
async def remove_vm(vm: VM):
    try:
        result = pve.remove_vm(vm)
        return {"message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    return pve.create_linked_clone(vm.name, vm.template_id, vm.node)

@app.post("/api/v1/pve/start-vm/{vm_name}")
def start_vm(vm_name: str):
    result = pve.start_vm(vm_name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/api/v1/pve/run-check-now")
async def run_pve_check_now():
    """Run all checks immediately."""
    try:
        pve.run_check_now()
        return {
            "message": "All PVE checks completed successfully",
            "steps": [
                "Schedule updates completed",
                "VM start checks completed",
                "Deletion checks completed"
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error running PVE checks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/pve/run-start-check")
async def run_vm_start_check():
    """Run only the VM start check process."""
    try:
        result = pve.check_vm_start_status()
        return {
            "message": "VM start check completed",
            "started_vms": result["started"],
            "already_running": result["already_running"],
            "failed_starts": result["failed"]
        }
    except Exception as e:
        logger.error(f"Error running VM start check: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/pve/run-deletion-check")
async def run_deletion_check():
    """Run only the VM deletion check process."""
    try:
        result = pve.remove_due_vms()
        return result
    except Exception as e:
        logger.error(f"Error running deletion check: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/pve/update-schedules")
async def update_vm_schedules():
    """Update deletion schedules for all VMs with end tags."""
    try:
        result = pve.update_all_vm_schedules()
        return {
            "message": "VM schedules updated successfully",
            "updated_vms": result["updated"],
            "removed_from_schedule": result["removed"],
            "total_scheduled_vms": result["total_scheduled"]
        }
    except Exception as e:
        logger.error(f"Error updating VM schedules: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update VM schedules: {str(e)}")

@app.get("/api/v1/pve/scheduled-deletions")
async def get_scheduled_deletions():
    """Get the current list of scheduled deletions."""
    try:
        result = pve.get_scheduled_deletions()
        return {
            "scheduled_deletions": result["scheduled_deletions"],
            "total_scheduled": len(result["scheduled_deletions"]),
            "total_due": result["total_due"],
            "due_vms": result["due_vms"]  # Adding the list of VMs due for deletion
        }
    except Exception as e:
        logger.error(f"Error getting scheduled deletions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/pve/scheduled-deletions")
async def clear_scheduled_deletions_endpoint():
    try:
        result = pve.clear_scheduled_deletions()
        return result
    except Exception as e:
        logger.error(f"Error clearing scheduled deletions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear scheduled deletions: {str(e)}")

@app.post("/api/v1/pve/shutdown-vm/{vm_name}")
def shutdown_vm(vm_name: str):
    return pve.shutdown_vm(vm_name)

@app.post("/api/v1/pve/remove-due")
async def remove_due_vms():
    """Remove all VMs that are past their deletion date."""
    try:
        result = pve.remove_due_vms()
        return result
    except Exception as e:
        logger.error(f"Error removing due VMs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/pve/remove-all-scheduled")
async def remove_all_scheduled_vms():
    try:
        result = pve.remove_all_scheduled_vms()
        return result
    except Exception as e:
        logger.error(f"Error removing all scheduled VMs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/pve/get-vm-mac-address/{vm_name}")
async def get_vm_mac_address_endpoint(vm_name: str):
    try:
        mac_address = pve.get_vm_mac_address(vm_name)
        if mac_address:
            return {"vm_name": vm_name, "mac_address": mac_address}
        else:
            raise HTTPException(status_code=404, detail=f"MAC address not found for VM: {vm_name}")
    except Exception as e:
        logger.error(f"Error getting MAC address for VM {vm_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get MAC address: {str(e)}")

@app.get("/api/v1/pve/vm-mac-addresses")
async def get_vm_mac_addresses():
    """Get MAC addresses for all VMs."""
    try:
        mac_addresses = pve.get_all_vm_mac_addresses()
        if mac_addresses is not None:
            return {"vm_mac_addresses": mac_addresses}
        else:
            raise HTTPException(status_code=500, detail="Failed to collect MAC addresses")
    except Exception as e:
        logger.error(f"Error in MAC address collection endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Nginx Proxy Manager endpoints
@app.post("/api/v1/nginx/create-proxy-host")
def create_proxy(proxy_host: ProxyHostCreate):
    try:
        result = nginx_proxy_manager.create_proxy_host(proxy_host.dict())
        return {"message": "Proxy host created successfully", "proxy_host_id": result["id"]}
    except requests.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create proxy host: {str(e)}")

@app.get("/api/v1/nginx/list-proxy-hosts")
def get_proxy_hosts():
    try:
        proxy_hosts = nginx_proxy_manager.list_proxy_hosts()
        return {"proxy_hosts": proxy_hosts}
    except requests.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list proxy hosts: {str(e)}")

@app.get("/api/v1/nginx/list-certificates")
def get_certificates():
    logger.debug("Received request to list certificates")
    try:
        certificates = nginx_proxy_manager.list_certificates()
        logger.info(f"Successfully retrieved {len(certificates)} certificates")
        return {"certificates": certificates}
    except requests.HTTPError as e:
        logger.error(f"HTTP error occurred: {e}")
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to list certificates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list certificates: {str(e)}")
    
@app.delete("/api/v1/nginx/proxy-hosts/{proxy_host_id}")
def delete_proxy_host(proxy_host_id: int):
    try:
        result = nginx_proxy_manager.delete_proxy_host(proxy_host_id)
        return {"message": f"Proxy host with ID {proxy_host_id} deleted successfully", "result": result}
    except requests.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete proxy host: {str(e)}")

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

@app.get("/api/v1/guacamole/list-users")
async def list_guacamole_users():
    users = guacamole.list_users()
    if users is not None:
        return {"users": users}
    else:
        raise HTTPException(status_code=500, detail="Failed to retrieve users from Guacamole")

@app.get("/api/v1/guacamole/connection-groups")
async def list_guacamole_connection_groups():
    """List all connection groups in Guacamole."""
    try:
        groups = guacamole.list_connection_groups()
        if groups is not None:
            return {"connection_groups": groups}
        else:
            raise HTTPException(status_code=500, detail="Failed to retrieve connection groups")
    except Exception as e:
        logger.error(f"Error listing connection groups: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/api/v1/guacamole/connection-groups")
async def create_guacamole_connection_group(group: ConnectionGroupCreate):
    """Create a new connection group in Guacamole."""
    try:
        result = guacamole.create_connection_group(
            name=group.name,
            parent_identifier=group.parent_identifier,
            type=group.type
        )
        if result:
            return {"message": f"Connection group '{group.name}' created successfully", "group": result}
        else:
            raise HTTPException(status_code=500, detail="Failed to create connection group")
    except Exception as e:
        logger.error(f"Error creating connection group: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/guacamole/connection-groups/{group_name}")
async def delete_guacamole_connection_group(group_name: str):
    """Delete a connection group by its name and all its contents recursively."""
    try:
        result = guacamole.delete_connection_group_by_name(group_name)
        
        if result['success']:
            return {
                "message": result['message'],
                "summary": result['summary']
            }
        else:
            raise HTTPException(
                status_code=404 if "No connection group found" in result['message'] else 500,
                detail={
                    "message": result['message'],
                    "summary": result['summary']
                }
            )
    except Exception as e:
        logger.error(f"Error deleting connection group: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

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

# Authentik endpoints
@app.post("/api/v1/authentik/users")
async def create_authentik_user(user: CreateAuthentikUserInput):
    try:
        result = authentik.create_user_if_not_exists(user.username, user.email, user.name, user.password)
        
        if "message" in result and "already exists" in result["message"]:
            # User already exists
            return {"message": result["message"]}
        else:
            # New user created
            return {"message": "User created successfully in Authentik with password set", "user": result}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/authentik/set_password")
async def set_authentik_user_password(username: str, password: str):
    try:
        user_id = authentik.get_user_id(username)
        result = authentik.set_user_password(user_id, password)
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/authentik/add-user-to-group")
async def add_authentik_user_to_group(input: AddAuthentikUserToGroupInput):
    try:
        # Convert group_id to int if necessary
        group_id = int(input.group_id) if input.group_id.isdigit() else input.group_id
        result = authentik.add_user_to_group(input.user_id, group_id)
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/v1/authentik/users/{username}")
async def get_authentik_user_id(username: str):
    try:
        user_id = authentik.get_user_id(username)
        return {"username": username, "user_id": user_id}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/authentik/groups/{group_name}")
async def get_authentik_group_id(group_name: str):
    try:
        group_id = authentik.get_group_id(group_name)
        return {"group_name": group_name, "group_id": group_id}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/authentik/users")
async def list_authentik_users():
    try:
        users = authentik.list_users()
        return {"users": users}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/authentik/groups")
async def list_authentik_groups():
    try:
        groups = authentik.list_groups()
        return {"groups": groups}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# FortiGate endpoints
@app.post("/api/v1/fortigate/add-dhcp-reservation")
async def add_dhcp_reservation(request: DHCPReservationRequest):
    try:
        assigned_ip = fortigate.add_dhcp_reservation(request.mac, request.seat, request.dhcp_server_id)
        if assigned_ip:
            return {"message": "DHCP reservation added successfully", "assigned_ip": assigned_ip, "mac": request.mac, "seat": request.seat, "dhcp_server_id": request.dhcp_server_id}
        else:
            raise HTTPException(status_code=400, detail="Failed to add DHCP reservation")
    except Exception as e:
        logger.error(f"Error adding DHCP reservation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add DHCP reservation: {str(e)}")

@app.post("/api/v1/fortigate/remove-dhcp-reservations")
async def remove_dhcp_reservations(request: DHCPRemovalRequest):
    try:
        removed_count = fortigate.remove_dhcp_reservations(request.seat_macs, request.dhcp_server_id)
        return {"message": f"Removed {removed_count} DHCP reservations", "seat_macs": request.seat_macs, "dhcp_server_id": request.dhcp_server_id}
    except Exception as e:
        logger.error(f"Error removing DHCP reservations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to remove DHCP reservations: {str(e)}")

@app.get("/api/v1/fortigate/validate-dhcp/{seat}/{dhcp_server_id}")
async def validate_dhcp_reservation(seat: str, dhcp_server_id: int):
    try:
        assigned_ip = fortigate.validate_dhcp_by_name(seat, dhcp_server_id)
        if assigned_ip:
            return {"seat": seat, "assigned_ip": assigned_ip, "dhcp_server_id": dhcp_server_id}
        else:
            raise HTTPException(status_code=404, detail=f"No DHCP reservation found for seat: {seat}")
    except Exception as e:
        logger.error(f"Error validating DHCP reservation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to validate DHCP reservation: {str(e)}")

@app.get("/api/v1/fortigate/get-dhcp-server-config/{dhcp_server_id}")
async def get_dhcp_server_config(dhcp_server_id: int):
    try:
        config = fortigate.get_dhcp_server_config(dhcp_server_id)
        if config:
            return {"dhcp_server_id": dhcp_server_id, "config": config}
        else:
            raise HTTPException(status_code=404, detail=f"No DHCP server configuration found for ID: {dhcp_server_id}")
    except Exception as e:
        logger.error(f"Error getting DHCP server configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get DHCP server configuration: {str(e)}")
    
@app.post("/api/v1/fortigate/add-dhcp-reservation-known-ip")
async def add_dhcp_reservation_known_ip_endpoint(request: DHCPReservationKnownIPRequest):
    try:
        result = fortigate.add_dhcp_reservation_known_ip(request.mac, request.seat, request.ip, request.dhcp_server_id)
        if result:
            return {"message": "DHCP reservation added successfully", "assigned_ip": result, "mac": request.mac, "seat": request.seat, "dhcp_server_id": request.dhcp_server_id}
        else:
            raise HTTPException(status_code=400, detail="Failed to add DHCP reservation")
    except Exception as e:
        logger.error(f"Error adding DHCP reservation with known IP: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add DHCP reservation: {str(e)}")
    
@app.get("/api/v1/fortigate/validate-dhcp/{dhcp_server_id}")
async def validate_dhcp(dhcp_server_id: int):
   try:
       vm_macs = pve.get_all_vm_mac_addresses()
       dhcp_config = fortigate.get_dhcp_server_config(dhcp_server_id)
       
       if not isinstance(dhcp_config, dict):
           raise HTTPException(status_code=500, detail=f"Invalid DHCP config type: {type(dhcp_config)}")
           
       reservations = dhcp_config.get('reserved-address', [])
       if not reservations:
           raise HTTPException(status_code=404, detail="No DHCP reservations found")

       valid_macs = {mac.lower() for vm_data in vm_macs.values() 
                    for mac in vm_data['interfaces'].values()}
       
       orphaned_reservations = [
           {
               'ip': res['ip'],
               'mac': res['mac'],
               'description': res['description']
           }
           for res in reservations
           if res['mac'].lower() not in valid_macs
       ]

       return {
           "message": f"Found {len(orphaned_reservations)} orphaned DHCP reservations",
           "orphaned_reservations": orphaned_reservations, 
           "total_dhcp_reservations": len(reservations),
           "total_vm_macs": len(valid_macs)
       }
       
   except Exception as e:
       logger.error(f"Error validating DHCP reservations: {str(e)}")
       raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
   
@app.post("/api/v1/fortigate/remove-orphaned-dhcp/{dhcp_server_id}")
async def remove_orphaned_dhcp(dhcp_server_id: int):
   try:
       orphaned = await validate_dhcp(dhcp_server_id) 
       removed_count = 0
       failed = []
       
       for reservation in orphaned['orphaned_reservations']:
           try:
               result = fortigate.remove_dhcp_reservations(seat_macs=[reservation['mac']], dhcp_server_id=dhcp_server_id)
               if result > 0:
                   removed_count += 1
               else:
                   failed.append(reservation['mac'])
           except Exception as e:
               failed.append(reservation['mac'])
               logger.error(f"Failed to remove {reservation['mac']}: {str(e)}")
               
       return {
           "removed_count": removed_count,
           "failed_macs": failed
       }
       
   except Exception as e:
       raise HTTPException(status_code=500, detail=str(e))

# Mounting PyWebIO app
app.mount("/", asgi_app(pywebio_main), name="pywebio")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
