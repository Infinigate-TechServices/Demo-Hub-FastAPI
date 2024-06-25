from proxmoxer import ProxmoxAPI
from models import TrainingSeat, VM, AddTagsRequest
import os
from dotenv import load_dotenv
import time
import threading
import json
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

# Get Proxmox connection details from environment variables
proxmox_host = os.getenv('PVE_HOST')
proxmox_user = os.getenv('PVE_USER')
proxmox_password = os.getenv('PVE_PASSWORD')
template_id = os.getenv('TEMPLATE_ID')
proxmox_port = int(os.getenv('PVE_PORT', 443))

# Initialize the Proxmox API client
proxmox = None

def authenticate_proxmox():
    global proxmox
    proxmox = ProxmoxAPI(
        host=proxmox_host,
        user=proxmox_user,
        password=proxmox_password,
        port=proxmox_port,
        verify_ssl=False
    )
    print("Authenticated with Proxmox")

# Authenticate initially
authenticate_proxmox()

# Function to refresh the authentication ticket periodically
def refresh_ticket():
    while True:
        time.sleep(7200 - 600)  # Sleep for 1 hour and 50 minutes
        try:
            authenticate_proxmox()
            print("Proxmox API ticket refreshed")
        except Exception as e:
            print(f"Failed to refresh Proxmox API ticket: {e}")

# Start the ticket refresh thread
ticket_refresh_thread = threading.Thread(target=refresh_ticket)
ticket_refresh_thread.daemon = True
ticket_refresh_thread.start()

# Dynamically get all PVE_NODE variables from .env
proxmox_nodes = []
index = 1
while True:
    node = os.getenv(f'PVE_NODE{index}')
    if node:
        proxmox_nodes.append(node)
    else:
        break
    index += 1

def evaluate_nodes():
    best_node = None
    max_memory = 0
    max_disk = 0

    for node in proxmox_nodes:
        status = proxmox.nodes(node).status().get()
        free_memory = status['memory']['free']
        free_disk = status['rootfs']['free']

        if free_memory > max_memory and free_disk > max_disk:
            max_memory = free_memory
            max_disk = free_disk
            best_node = node

    return best_node

def create_training_seat(name: str, template_id: int):
    best_node = evaluate_nodes()
    if not best_node:
        return {"error": "No suitable node found"}

    # Correctly get the next available VMID
    vmid = proxmox.cluster.nextid.get()
    return proxmox.nodes(best_node).qemu(template_id).post('clone', vmid=template_id, newid=vmid, name=name, full=1)

def remove_training_seat(seat: TrainingSeat):
    for node in proxmox_nodes:
        vms = proxmox.nodes(node).qemu().get()
        for vm in vms:
            if vm['name'] == seat.name:
                vmid = vm['vmid']
                return proxmox.nodes(node).qemu(vmid).delete()
    return {"error": "VM not found"}

def create_linked_clone(name: str, template_id: int):
    best_node = evaluate_nodes()
    if not best_node:
        return {"error": "No suitable node found"}
    
    vmid = proxmox.cluster.nextid.get()
    return proxmox.nodes(best_node).qemu(template_id).post('clone', vmid=template_id, newid=vmid, name=name, full=0)

def remove_vm(vm: VM):
    vmid = get_vm_id(vm.name)
    if vmid is not None:
        for node in proxmox_nodes:
            try:
                proxmox.nodes(node).qemu(vmid).delete()
                return f"VM '{vm.name}' with ID {vm.id} has been removed."
            except Exception as e:
                continue
        return f"Failed to remove VM '{vm.name}'."
    else:
        return f"VM '{vm.name}' not found."
 
def list_vms():
    vms_list = []
    for node in proxmox_nodes:
        vms = proxmox.nodes(node).qemu().get()
        vms_list.extend(vms)
    return vms_list

def get_vm_id(vm_name):
    logger.debug(f"Searching for VM with name: {vm_name}")
    for node in proxmox.nodes.get():
        logger.debug(f"Checking node: {node['node']}")
        for vm in proxmox.nodes(node['node']).qemu.get():
            logger.debug(f"Found VM: {vm['name']} (ID: {vm['vmid']})")
            if vm['name'] == vm_name:
                logger.info(f"VM found: {vm_name} (ID: {vm['vmid']})")
                return vm['vmid']
    logger.warning(f"VM not found: {vm_name}")
    return None

def find_seat_ip(vm_name: str) -> str:
    for node in proxmox.nodes.get():
        for vm in proxmox.nodes(node['node']).qemu.get():
            if vm['name'] == vm_name:
                try:
                    command = "pct exec 100 -- bash -c \"ip -4 addr show eth0 | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}'\""
                    result = proxmox.nodes(node['node']).qemu(vm['vmid']).agent.exec.post(command=command)
                    
                    pid = result['pid']
                    
                    for _ in range(30):  # Try for 30 seconds
                        time.sleep(1)
                        status = proxmox.nodes(node['node']).qemu(vm['vmid']).agent('exec-status').get(pid=pid)
                        if status['exited']:
                            if 'out-data' in status:
                                return status['out-data'].strip()
                            break
                except Exception as e:
                    print(f"Error processing VM {vm_name}: {str(e)}")
    return None

def add_tags_to_vm(request: AddTagsRequest):
    logger.info(f"Attempting to add tags to VM: {request.vm_name}")
    logger.debug(f"Tags to add: {request.tags}")
    
    # Convert tags to a comma-separated string
    tags_string = ','.join(request.tags)
    logger.debug(f"Tags string: {tags_string}")
    
    vmid = get_vm_id(request.vm_name)
    if vmid is None:
        raise ValueError(f"VM with name {request.vm_name} not found")
    
    for node in proxmox.nodes.get():
        try:
            logger.debug(f"Updating tags for VM {request.vm_name} (ID: {vmid}) on node {node['node']}")
            logger.debug(f"Proxmox API call: proxmox.nodes('{node['node']}').qemu({vmid}).config.put(tags='{tags_string}')")
            proxmox.nodes(node['node']).qemu(vmid).config.put(tags=tags_string)
            logger.info(f"Tags updated successfully for VM {request.vm_name}")
            return True
        except Exception as e:
            logger.error(f"Error adding tags to VM {request.vm_name}: {str(e)}")
    
    logger.warning(f"Failed to add tags to VM {request.vm_name} on any node")
    return False

def start_vm(vm_name: str):
    vmid = get_vm_id(vm_name)
    if vmid is None:
        return {"error": f"VM '{vm_name}' not found"}
    
    for node in proxmox_nodes:
        try:
            proxmox.nodes(node).qemu(vmid).status.start.post()
            return {"message": f"VM '{vm_name}' started successfully"}
        except Exception as e:
            logger.error(f"Error starting VM '{vm_name}': {str(e)}")
            return {"error": f"Exception occurred while starting VM '{vm_name}': {str(e)}"}

    return {"error": f"VM '{vm_name}' could not be started on any node"}