from proxmoxer import ProxmoxAPI
from models import TrainingSeat
import os
from dotenv import load_dotenv

load_dotenv()

# Get Proxmox connection details from environment variables
proxmox_host = os.getenv('PVE_HOST')
proxmox_user = os.getenv('PVE_USER')
proxmox_password = os.getenv('PVE_PASSWORD')
proxmox_node = os.getenv('PVE_NODE')
proxmox_port = int(os.getenv('PVE_PORT', 443))

# Connect to Proxmox API
proxmox = ProxmoxAPI(
    host=proxmox_host,
    user=proxmox_user,
    password=proxmox_password,
    port=proxmox_port,
    verify_ssl=False
)

def create_training_seat(seat: TrainingSeat, template_id: int):
    # Correctly get the next available VMID
    vmid = proxmox.cluster.nextid.get()
    # Perform the clone operation
    return proxmox.nodes(proxmox_node).qemu(template_id).clone.create(
        newid=vmid,
        name=seat.name,
        full=1  # Use 1 for true
    )

def remove_training_seat(seat: TrainingSeat):
    vms = proxmox.nodes(proxmox_node).qemu().get()
    for vm in vms:
        if vm['name'] == seat.name:
            vmid = vm['vmid']
            return proxmox.nodes(proxmox_node).qemu(vmid).delete()
    return {"error": "VM not found"}

def list_vms():
    vms = proxmox.nodes(proxmox_node).qemu().get()
    print("VMs retrieved from Proxmox:", vms)  # Debugging line
    return vms