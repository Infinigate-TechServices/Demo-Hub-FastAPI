from pywebio.input import actions, input, input_group, NUMBER, checkbox, TEXT
from pywebio.output import put_text, put_table, put_error, put_buttons
from pywebio.session import run_js
import requests

API_BASE_URL = "http://localhost:8081/api"

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
                response = requests.post(f"{API_BASE_URL}/v1/dns/create-record-a", json={"domain": domain, "ip": ip})
                if response.status_code == 200:
                    put_text("Record created successfully!")
                else:
                    put_error("Failed to create record.")
            elif dns_choice == 'Remove Record':
                record_id = input("Enter Record ID")
                response = requests.post(f"{API_BASE_URL}/v1/dns/remove-record-a", json={"id": record_id})
                if response.status_code == 200:
                    put_text("Record removed successfully!")
                else:
                    put_error("Failed to remove record.")
            elif dns_choice == 'List Records':
                response = requests.get(f"{API_BASE_URL}/v1/dns/list-seats")
                if response.status_code == 200:
                    records = response.json()
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
                response = requests.get(f"{API_BASE_URL}/v1/dns/list-seats")
                if response.status_code == 200:
                    records = response.json()
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
                response = requests.post(f"{API_BASE_URL}/v1/pve/create-training-seat", json={
                    "name": vm_details['name'],
                    "template_id": vm_details['template_id']
                })
                if response.status_code == 200:
                    put_text("VM created successfully!")
                else:
                    put_error("Failed to create VM.")
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
            elif pve_choice == 'Remove VM':
                name = input("Enter VM name")
                response = requests.post(f"{API_BASE_URL}/v1/pve/remove-training-seat", json={"name": name})
                if response.status_code == 200:
                    put_text("VM removed successfully!")
                else:
                    put_error("Failed to remove VM.")
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
            elif pve_choice == 'List VMs':
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
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
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
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
            elif pve_choice == 'Create Multiple VMs':
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
                put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))
            elif pve_choice == 'Delete Multiple VMs':
                response = requests.get(f"{API_BASE_URL}/v1/pve/list-vms")
                if response.status_code == 200:
                    vms = response.json()
                    # Filter out templates
                    vms = [vm for vm in vms if '-Template' not in vm.get('name', '')]
                    vm_names = [vm.get('name') for vm in vms]
                    selected_vms = checkbox("Select VMs to delete", options=vm_names)
                    for vm_name in selected_vms:
                        response = requests.post(f"{API_BASE_URL}/v1/pve/remove-training-seat", json={"name": vm_name})
                        if response.status_code != 200:
                            put_error(f"Failed to remove VM {vm_name}.")
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
                proxy_host = {
                    "domain_names": domain_names,
                    "forward_host": data['forward_host'],
                    "forward_port": data['forward_port'],
                    "access_list_id": data['access_list_id'] if data['access_list_id'] != 0 else None,
                    "certificate_id": data['certificate_id'] if data['certificate_id'] != 0 else None,
                    "ssl_forced": bool(data['ssl_forced']),
                    "caching_enabled": bool(data['caching_enabled']),
                    "block_exploits": bool(data['block_exploits']),
                    "advanced_config": data['advanced_config'],
                    "allow_websocket_upgrade": bool(data['allow_websocket_upgrade']),
                    "http2_support": bool(data['http2_support']),
                    "forward_scheme": data['forward_scheme'],
                    "enabled": bool(data['enabled']),
                    "hsts_enabled": bool(data['hsts_enabled']),
                    "hsts_subdomains": bool(data['hsts_subdomains']),
                    "meta": {},
                    "locations": []
                }
                response = requests.post(f"{API_BASE_URL}/v1/nginx/create-proxy-host", json=proxy_host)
                if response.status_code == 200:
                    put_text("Proxy host created successfully!")
                    put_text(response.json())
                else:
                    put_error("Failed to create proxy host.")
                put_buttons(['Return to Nginx Management'], onclick=lambda _: run_js('location.reload()'))
            elif nginx_choice == 'Remove Proxy Host':
                proxy_host_id = input("Enter Proxy Host ID to Remove", type=NUMBER)
                response = requests.delete(f"{API_BASE_URL}/v1/nginx/remove-proxy-host/{proxy_host_id}")
                if response.status_code == 200:
                    put_text("Proxy host removed successfully!")
                    put_text(response.json())
                else:
                    put_error("Failed to remove proxy host.")
                put_buttons(['Return to Nginx Management'], onclick=lambda _: run_js('location.reload()'))
            elif nginx_choice == 'List Proxy Hosts':
                response = requests.get(f"{API_BASE_URL}/v1/nginx/list-proxy-hosts")
                if response.status_code == 200:
                    hosts = response.json()
                    table_data = [["ID", "Domain Names", "Forward Host", "Forward Port"]]
                    for host in hosts:
                        table_data.append([host['id'], ', '.join(host['domain_names']), host['forward_host'], host['forward_port']])
                    put_table(table_data)
                else:
                    put_error("Failed to retrieve proxy hosts.")
                put_buttons(['Return to Nginx Management'], onclick=lambda _: run_js('location.reload()'))
            elif nginx_choice == 'Return to Main Menu':
                continue

def format_memory(mem):
    # Convert memory from bytes to GB
    return f"{mem / (1024**3):.2f} GB"

def format_cpu(cpu):
    # Convert CPU usage to percentage
    return f"{cpu * 100:.2f} %"
