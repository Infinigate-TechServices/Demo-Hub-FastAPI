from pywebio.input import actions, input, input_group, NUMBER, checkbox, TEXT
from pywebio.output import put_text, put_table, put_error, put_buttons
from pywebio.session import run_js, go_app
from models import RecordA, TrainingSeat, ProxyHost
import cf
import pve
from nginx_proxy_manager import list_proxy_hosts create_proxy_host remove_proxy_host

def pywebio_main():
    while True:
        choice = actions('Choose an option', ['DNS Management', 'PVE Management', 'Nginx Proxy Management'])
        if choice == 'DNS Management':
            dns_choice = actions('Choose DNS action', [
                'Create Record', 'Remove Record', 'List Records', 'List Training Records', 'Return to Main Menu'
            ])
            if dns_choice == 'Create Record':
                domain = input("Enter domain")
                ip = input("Enter IP")
                cf.create_record_a(RecordA(domain=domain, ip=ip))
                put_text("Record created successfully!")
            elif dns_choice == 'Remove Record':
                record_id = input("Enter Record ID")
                cf.remove_record_a(RecordA(id=record_id))
                put_text("Record removed successfully!")
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
            if dns_choice == 'Return to Main Menu':
                continue

        elif choice == 'PVE Management':
            pve_choice = actions('Choose PVE action', [
                'Create VM', 'Remove VM', 'List VMs', 'List Templates', 'Create Multiple VMs', 'Delete Multiple VMs', 'Return to Main Menu'
            ])
            if pve_choice == 'Create VM':
                vm_details = input_group("Enter VM details", [
                    input("Enter VM name", name='name'),
                    input("Enter Template ID", name='template_id', type=NUMBER)
                ])
                pve.create_training_seat(TrainingSeat(name=vm_details['name']), vm_details['template_id'])
                put_text("VM created successfully!")
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
            elif pve_choice == 'Remove VM':
                name = input("Enter VM name")
                pve.remove_training_seat(TrainingSeat(name=name))
                put_text("VM removed successfully!")
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
            elif pve_choice == 'Return to Main Menu':
                continue

        elif choice == 'Nginx Proxy Management':
            nginx_choice = actions('Choose Nginx Proxy action', [
                'Create Proxy Host', 'Remove Proxy Host', 'List Proxy Hosts', 'Return to Main Menu'
            ])
            if nginx_choice == 'Create Proxy Host':
                data = input_group("Create Proxy Host", [
                    input("Domain Names (comma separated)", name="domain_names", type=TEXT),
                    input("Forward Host", name="forward_host", type=TEXT),
                    input("Forward Port", name="forward_port", type=NUMBER),
                    input("Access List ID", name="access_list_id", type=NUMBER, value=0),
                    input("Certificate ID", name="certificate_id", type=NUMBER, value=0),
                    input("SSL Forced", name="ssl_forced", type=NUMBER, value=0),
                    input("Caching Enabled", name="caching_enabled", type=NUMBER, value=0),
                    input("Block Exploits", name="block_exploits", type=NUMBER, value=0),
                    input("Advanced Config", name="advanced_config", type=TEXT, value=""),
                    input("Allow Websocket Upgrade", name="allow_websocket_upgrade", type=NUMBER, value=0),
                    input("HTTP2 Support", name="http2_support", type=NUMBER, value=0),
                    input("Forward Scheme", name="forward_scheme", type=TEXT, value="http"),
                    input("Enabled", name="enabled", type=NUMBER, value=1),
                    input("HSTS Enabled", name="hsts_enabled", type=NUMBER, value=0),
                    input("HSTS Subdomains", name="hsts_subdomains", type=NUMBER, value=0),
                    input("Use Default Location", name="use_default_location", type=NUMBER, value=1),
                    input("IPv6", name="ipv6", type=NUMBER, value=1)
                ])
                domain_names = [domain.strip() for domain in data['domain_names'].split(',')]
                proxy_host = ProxyHost(
                    domain_names=domain_names,
                    forward_host=data['forward_host'],
                    forward_port=data['forward_port'],
                    access_list_id=data['access_list_id'],
                    certificate_id=data['certificate_id'],
                    ssl_forced=data['ssl_forced'],
                    caching_enabled=data['caching_enabled'],
                    block_exploits=data['block_exploits'],
                    advanced_config=data['advanced_config'],
                    allow_websocket_upgrade=data['allow_websocket_upgrade'],
                    http2_support=data['http2_support'],
                    forward_scheme=data['forward_scheme'],
                    enabled=data['enabled'],
                    hsts_enabled=data['hsts_enabled'],
                    hsts_subdomains=data['hsts_subdomains'],
                    use_default_location=bool(data['use_default_location']),
                    ipv6=bool(data['ipv6'])
                )
                result = create_proxy_host(proxy_host)
                put_text("Proxy host created successfully!")
                put_text(result)
                put_buttons(['Return to Nginx Management'], [lambda: go_app('nginx_management', new_window=False)])
            elif nginx_choice == 'Remove Proxy Host':
                proxy_host_id = input("Enter Proxy Host ID to Remove", type=NUMBER)
                result = remove_proxy_host(proxy_host_id)
                put_text("Proxy host removed successfully!")
                put_text(result)
                put_buttons(['Return to Nginx Management'], [lambda: go_app('nginx_management', new_window=False)])
            elif nginx_choice == 'List Proxy Hosts':
                hosts = list_proxy_hosts()
                table_data = [["ID", "Domain Names", "Forward Host", "Forward Port"]]
                for host in hosts:
                    table_data.append([host['id'], ', '.join(host['domain_names']), host['forward_host'], host['forward_port']])
                put_table(table_data)
                put_buttons(['Return to Nginx Management'], [lambda: go_app('nginx_management', new_window=False)])
            elif nginx_choice == 'Return to Main Menu':
                continue

def format_memory(mem):
    # Convert memory from bytes to GB
    return f"{mem / (1024**3):.2f} GB"

def format_cpu(cpu):
    # Convert CPU usage to percentage
    return f"{cpu * 100:.2f} %"
