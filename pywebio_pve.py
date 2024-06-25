from pywebio.input import actions, input, input_group, NUMBER, checkbox
from pywebio.output import put_text, put_table, put_error, put_buttons
from pywebio.session import run_js
import requests
import time

API_BASE_URL = "http://localhost:8081/api"

def pve_management():
    pve_choice = actions('Choose PVE action', [
        'List VMs', 'List Templates', 'Create VMs', 'Remove VMs', 'Find Seat IP', 'Return to Main Menu'
    ])
    if pve_choice == 'List VMs':
        response = requests.get(f"{API_BASE_URL}/v1/pve/list-vms")
        if response.status_code == 200:
            vms = response.json()
            # Filter out templates
            vms = [vm for vm in vms if '-Template' not in vm.get('name', '')]
            # Sort the VMs by CPU load in descending order
            vms.sort(key=lambda vm: vm.get('cpu', 0), reverse=True)
            
            table_data = [["VMID", "Name", "Status", "Memory", "CPU"]]
            for vm in vms:
                max_memory = format_memory(vm.get('maxmem'))
                cpu = format_cpu(vm.get('cpu'))
                table_data.append([vm.get('vmid'), vm.get('name'), vm.get('status'), max_memory, cpu])
            put_table(table_data)
        else:
            put_error("Failed to retrieve VMs.")
    elif pve_choice == 'List Templates':
        response = requests.get(f"{API_BASE_URL}/v1/pve/list-vms")
        if response.status_code == 200:
            vms = response.json()
            # Filter to get only templates
            templates = [vm for vm in vms if '-Template' in vm.get('name', '')]
            table_data = [["VMID", "Name"]]  # Removed Status, Memory, and CPU columns
            for vm in templates:
                table_data.append([vm.get('vmid'), vm.get('name')])
            put_table(table_data)
        else:
            put_error("Failed to retrieve templates.")
    elif pve_choice == 'Create VMs':
        num_vms = input("Enter number of VMs to create", type=NUMBER)
        
        # List available templates
        response = requests.get(f"{API_BASE_URL}/v1/pve/list-vms")
        if response.status_code == 200:
            vms = response.json()
            templates = [vm for vm in vms if '-Template' in vm.get('name', '')]
            template_options = [f"{vm.get('name')} (ID: {vm.get('vmid')})" for vm in templates]
            selected_template = checkbox("Select a template for the VMs", options=template_options, required=True)[0]
            selected_template_id = int(selected_template.split("ID: ")[1].rstrip(")"))
            
            # Input fields for VM names
            vm_name_fields = [input(f"Enter name for VM {i + 1}", name=f'vm_name_{i}') for i in range(num_vms)]
            vm_details = input_group("Enter names for the VMs", vm_name_fields)
            
            for i in range(num_vms):
                vm_name = vm_details[f'vm_name_{i}']
                response = requests.post(f"{API_BASE_URL}/v1/pve/create-training-seat", json={
                    "name": vm_name,
                    "template_id": selected_template_id
                })
                if response.status_code != 200:
                    put_error(f"Failed to create VM {vm_name}.")
            put_text("VMs created successfully!")
        else:
            put_error("Failed to retrieve templates.")
    elif pve_choice == 'Remove VMs':
        response = requests.get(f"{API_BASE_URL}/v1/pve/list-vms")
        if response.status_code == 200:
            vms = response.json()
            # Filter out templates
            vms = [vm for vm in vms if '-Template' not in vm.get('name', '')]
            vm_names = [vm.get('name') for vm in vms]
            selected_vms = checkbox("Select VMs to delete", options=vm_names)
            for vm_name in selected_vms:
                #response = requests.post(f"{API_BASE_URL}/v1/pve/remove-training-seat", json={"name": vm_name})
                response = requests.post(f"{API_BASE_URL}/v1/pve/remove-vm", json={"name": vm_name})
                if response.status_code != 200:
                    put_error(f"Failed to remove VM {vm_name}.")
            put_text("Selected VMs deleted successfully!")
        else:
            put_error("Failed to retrieve VMs.")
    elif pve_choice == 'Find Seat IP':
        find_seat_ip()
    elif pve_choice == 'Return to Main Menu':
        run_js('location.reload()')

def find_seat_ip():
    vm_name = input("Enter VM name to find seat IP", required=True)
    put_text(f"Searching for IP of seat '{vm_name}'...")
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = requests.get(f"{API_BASE_URL}/v1/pve/find-seat-ip/{vm_name}", timeout=60)
            response.raise_for_status()
            
            data = response.json()
            if 'ip_address' in data:
                put_text(f"IP address for seat '{vm_name}': {data['ip_address']}")
                return
            else:
                put_text(f"Unexpected response format: {data}")
            
        except requests.exceptions.Timeout:
            put_text(f"Request timed out (attempt {attempt + 1}/{max_retries}). Retrying...")
            time.sleep(5)
        except requests.exceptions.RequestException as e:
            put_error(f"An error occurred: {str(e)}")
            return
    
    put_error(f"Failed to retrieve IP for seat '{vm_name}' after {max_retries} attempts.")

def format_memory(mem):
    # Convert memory from bytes to GB
    return f"{mem / (1024**3):.2f} GB"

def format_cpu(cpu):
    # Convert CPU usage to percentage
    return f"{cpu * 100:.2f} %"

if __name__ == '__main__':
    pve_management()
