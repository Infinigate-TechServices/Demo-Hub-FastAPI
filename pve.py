from proxmoxer import ProxmoxAPI
from models import TrainingSeat, VM
import os
from dotenv import load_dotenv
import time
import threading

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
    return proxmox.nodes(best_node).qemu().post('clone', vmid=template_id, newid=vmid, name=name, full=True)


def remove_training_seat(seat: TrainingSeat):
    for node in proxmox_nodes:
        vms = proxmox.nodes(node).qemu().get()
        for vm in vms:
            if vm['name'] == seat.name:
                vmid = vm['vmid']
                return proxmox.nodes(node).qemu(vmid).delete()
    return {"error": "VM not found"}

def list_vms():
    vms_list = []
    for node in proxmox_nodes:
        vms = proxmox.nodes(node).qemu().get()
        vms_list.extend(vms)
    return vms_list
