from pywebio.input import actions, input, input_group, NUMBER, checkbox
from pywebio.output import put_text, put_table, put_error, put_buttons
from pywebio.session import run_js
from models import RecordA, TrainingSeat
import cf
import pve

def pywebio_main():
    while True:
        choice = actions('Choose an option', ['DNS Management', 'PVE Management'])
        if choice == 'DNS Management':
            dns_choice = actions('Choose DNS action', ['Create Record', 'Remove Record', 'List Records', 'List Training Records'])
            if dns_choice == 'Create Record':
                domain = input("Enter domain")
                ip = input("Enter IP")
                cf.create_record_a(RecordA(domain=domain, ip=ip))
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
            elif dns_choice == 'Remove Record':
                record_id = input("Enter Record ID")
                cf.remove_record_a(RecordA(id=record_id))
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
            elif dns_choice == 'List Records':
                records = cf.list_seats()
                if isinstance(records, list):
                    table_data = [["ID", "Name", "Content", "TTL", "Comment"]]
                    for record in records:
                        table_data.append([
                            record.get('id'),
                            record.get('name'),
                            record.get('content'),
                            record.get('ttl'),
                            record.get('comment')
                        ])
                    put_table(table_data)
                else:
                    put_error("Failed to retrieve DNS records.")
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
            elif dns_choice == 'List Training Records':
                records = cf.list_seats()
                if isinstance(records, list):
                    # Filter records for the subdomain student.infinigate-labs.com
                    training_records = [record for record in records if record.get('name').endswith('student.infinigate-labs.com')]
                    table_data = [["ID", "Name", "Content", "TTL", "Comment"]]
                    for record in training_records:
                        table_data.append([
                            record.get('id'),
                            record.get('name'),
                            record.get('content'),
                            record.get('ttl'),
                            record.get('comment')
                        ])
                    put_table(table_data)
                else:
                    put_error("Failed to retrieve DNS records.")
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
        elif choice == 'PVE Management':
            pve_choice = actions('Choose PVE action', ['Create VM', 'Remove VM', 'List VMs', 'List Templates', 'Create Multiple VMs', 'Delete Multiple VMs'])
            if pve_choice == 'Create VM':
                vm_details = input_group("Enter VM details", [
                    input("Enter VM name", name='name'),
                    input("Enter Template ID", name='template_id', type=NUMBER)
                ])
                pve.create_training_seat(TrainingSeat(name=vm_details['name']), vm_details['template_id'])
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
            elif pve_choice == 'Remove VM':
                name = input("Enter VM name")
                pve.remove_training_seat(TrainingSeat(name=name))
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
            elif pve_choice == 'List VMs':
                vms = pve.list_vms()
                if isinstance(vms, list):
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
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
            elif pve_choice == 'List Templates':
                vms = pve.list_vms()
                if isinstance(vms, list):
                    # Filter to get only templates
                    templates = [vm for vm in vms if '-Template' in vm.get('name', '')]
                    table_data = [["VMID", "Name"]]  # Removed Status, Memory, and CPU columns
                    for vm in templates:
                        table_data.append([vm.get('vmid'), vm.get('name')])
                    put_table(table_data)
                else:
                    put_error("Failed to retrieve templates.")
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
            elif pve_choice == 'Create Multiple VMs':
                num_vms = input("Enter number of VMs to create", type=NUMBER)
                
                # List available templates
                vms = pve.list_vms()
                if isinstance(vms, list):
                    templates = [vm for vm in vms if '-Template' in vm.get('name', '')]
                    template_options = [f"{vm.get('name')} (ID: {vm.get('vmid')})" for vm in templates]
                    selected_template = checkbox("Select a template for the VMs", options=template_options, required=True)[0]
                    selected_template_id = int(selected_template.split("ID: ")[1].rstrip(")"))
                    
                    # Input fields for VM names
                    vm_name_fields = [input(f"Enter name for VM {i + 1}", name=f'vm_name_{i}') for i in range(num_vms)]
                    vm_details = input_group("Enter names for the VMs", vm_name_fields)
                    
                    for i in range(num_vms):
                        vm_name = vm_details[f'vm_name_{i}']
                        pve.create_training_seat(TrainingSeat(name=vm_name), selected_template_id)
                    put_text("VMs created successfully!")
                else:
                    put_error("Failed to retrieve templates.")
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
            elif pve_choice == 'Delete Multiple VMs':
                vms = pve.list_vms()
                if isinstance(vms, list):
                    # Filter out templates
                    vms = [vm for vm in vms if '-Template' not in vm.get('name', '')]
                    vm_names = [vm.get('name') for vm in vms]
                    selected_vms = checkbox("Select VMs to delete", options=vm_names)
                    for vm_name in selected_vms:
                        pve.remove_training_seat(TrainingSeat(name=vm_name))
                    put_text("Selected VMs deleted successfully!")
                else:
                    put_error("Failed to retrieve VMs.")
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))

def format_memory(mem):
    # Convert memory from bytes to GB
    return f"{mem / (1024**3):.2f} GB"

def format_cpu(cpu):
    # Convert CPU usage to percentage
    return f"{cpu * 100:.2f} %"
