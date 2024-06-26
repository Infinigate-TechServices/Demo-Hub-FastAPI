from pywebio.input import input, checkbox, input_group, NUMBER, select
from pywebio.output import put_text, put_error, put_loading, put_info, put_success, clear, put_warning
import requests
from datetime import datetime
import time
import re
import unidecode
import json

API_BASE_URL = "http://localhost:8081/api"

# Load training templates from JSON
with open("training_templates.json") as file:
    training_templates = json.load(file)

def sanitize_name(name):
    # Remove leading/trailing whitespace
    name = name.strip()
    
    # Replace multiple spaces with a single space
    name = re.sub(r'\s+', ' ', name)
    
    # Replace umlauts with their two-letter equivalents
    umlaut_map = {
        'ä': 'ae',
        'ö': 'oe',
        'ü': 'ue',
        'Ä': 'Ae',
        'Ö': 'Oe',
        'Ü': 'Ue',
        'ß': 'ss'
    }
    for umlaut, replacement in umlaut_map.items():
        name = name.replace(umlaut, replacement)
    
    # Remove any characters that aren't letters, spaces, or hyphens
    name = re.sub(r'[^a-zA-Z\s-]', '', name)
    
    # Replace any remaining diacritical marks
    name = unidecode.unidecode(name)
    
    # Replace spaces with dashes
    name = name.replace(' ', '-')
    
    # Capitalize each word (now separated by dashes)
    name = '-'.join(word.capitalize() for word in name.split('-'))
    
    return name

def create_training_seats():
    # Load training templates from JSON
    with open("training_templates.json") as file:
        training_templates = json.load(file)
            
    put_info("Fetching available templates...")
    response = requests.get(f"{API_BASE_URL}/v1/pve/list-vms")
    if response.status_code != 200:
        clear()
        put_error("Failed to retrieve templates.")
        return

    clear()
    vms = response.json()
    templates = [vm for vm in vms if '-Template' in vm.get('name', '')]
    template_options = [f"{vm.get('name')} (ID: {vm.get('vmid')})" for vm in templates]

    # Get available training options from training_templates.json
    training_options = [template["name"] for template in training_templates]

    # Ask the user to select the desired training and VM template
    selections = input_group("Select the training and VM template", [
        select("Training", name="selected_training", options=training_options, required=True),
        checkbox("VM Template", name="selected_template", options=template_options, required=True)
    ])

    selected_training = selections["selected_training"]
    selected_template = selections["selected_template"][0]
    selected_template_id = int(selected_template.split("ID: ")[1].rstrip(")"))
    selected_template_name = selected_template.split(" (ID:")[0].replace("-Template", "")

    num_seats = input("Enter number of seats to create", type=NUMBER)

    training_dates = input_group("Enter training dates", [
        input("Training Start Date (DD-MM-YYYY)", name="start_date", required=True),
        input("Training End Date (DD-MM-YYYY)", name="end_date", required=True)
    ])

    seats = []
    for i in range(num_seats):
        while True:
            seat_info = input_group(f"Enter details for seat {i + 1}", [
                input("First Name", name="first_name", required=True),
                input("Last Name", name="last_name", required=True),
            ])
            
            first_name = sanitize_name(seat_info['first_name'])
            last_name = sanitize_name(seat_info['last_name'])
            
            if first_name and last_name:
                break
            else:
                put_error("Names cannot be empty. Please enter valid names.")

        vm_name = f"{first_name}-{last_name}-{selected_template_name}"
        seats.append({
            "name": vm_name,
            "template_id": selected_template_id,
            "first_name": first_name,
            "last_name": last_name,
        })

    # Define group options
    group_options = [
        ("Trainingsteilnehmer", 6),
        ("Trainingsteilnehmer ohne Mail", 10)
    ]

    # Ask for the group selection
    selected_group = select("Select the group for the students", options=[g[0] for g in group_options])
    selected_group_id = next(g[1] for g in group_options if g[0] == selected_group)

    total_steps = len(seats) * 10  # Adjust the number of steps if needed
    current_step = 0

    for idx, seat in enumerate(seats):
        # Step 1: Create VM
        current_step += 1
        put_info(f"Creating VM for {seat['name']}... ({current_step}/{total_steps})")
        with put_loading():
            response = requests.post(f"{API_BASE_URL}/v1/pve/create-linked-clone", json={
                "name": seat['name'],
                "template_id": seat['template_id']
            })
        if response.status_code != 200:
            put_error(f"Failed to create VM for {seat['name']}.")
            continue

        time.sleep(5)

        # Step 2: Adding tags to VM
        current_step += 1
        put_info(f"Adding tags to VM {seat['name']}... ({current_step}/{total_steps})")
        tags = [
            f"start-{training_dates['start_date']}",
            f"end-{training_dates['end_date']}"
        ]
        with put_loading():
            response = requests.post(f"{API_BASE_URL}/v1/pve/add-tags-to-vm", json={
                "vm_name": seat['name'],
                "tags": tags
            })
        if response.status_code != 200:
            put_error(f"Failed to add tags to VM {seat['name']}. Error: {response.text}")

        time.sleep(5)

        # Step 3: Starting VM
        current_step += 1
        put_info(f"Starting VM {seat['name']}... ({current_step}/{total_steps})")
        with put_loading():
            response = requests.post(f"{API_BASE_URL}/v1/pve/start-vm/{seat['name']}")
        if response.status_code != 200:
            put_error(f"Failed to start VM {seat['name']}. Error: {response.text}")

        time.sleep(5)

        # Step 4: Create User in LDAP
        current_step += 1
        put_info(f"Creating LDAP user for {seat['first_name']} {seat['last_name']}... ({current_step}/{total_steps})")
        lldap_user_data = {
            "id": f"{seat['first_name'].lower()}.{seat['last_name'].lower()}",
            "email": f"{seat['first_name'].lower()}.{seat['last_name'].lower()}@infinigate-labs.com",
            "displayName": f"{seat['first_name']} {seat['last_name']}",
            "firstName": seat['first_name'],
            "lastName": seat['last_name']
        }
        with put_loading():
            response = requests.post(f"{API_BASE_URL}/v1/lldap/users", json=lldap_user_data)
        if response.status_code != 200:
            put_error(f"Failed to create LLDAP user for {seat['name']}. Error: {response.text}")
            continue

        time.sleep(5)

        # Step 5: Add user to group in LDAP
        current_step += 1
        put_info(f"Adding user {seat['first_name']} {seat['last_name']} to group... ({current_step}/{total_steps})")
        add_to_group_data = {
            "userId": lldap_user_data["id"],
            "groupId": selected_group_id
        }
        with put_loading():
            response = requests.post(f"{API_BASE_URL}/v1/lldap/add-user-to-group", json=add_to_group_data)
        if response.status_code != 200:
            put_error(f"Failed to add user {seat['name']} to group. Error: {response.text}")

        time.sleep(2)

        # Step 6: Create User in Guacamole
        current_step += 1
        put_info(f"Creating Guacamole user for {seat['first_name']} {seat['last_name']}... ({current_step}/{total_steps})")
        guacamole_username = f"{seat['first_name'].lower()}.{seat['last_name'].lower()}@infinigate-labs.com"
        with put_loading():
            response = requests.post(f"{API_BASE_URL}/v1/guacamole/users/{guacamole_username}")
        if response.status_code != 200:
            put_error(f"Failed to create Guacamole user for {seat['name']}. Error: {response.text}")

        time.sleep(2)

        # Step 7: Find Proxmox Seat IP
        current_step += 1
        put_info(f"Finding Proxmox IP for seat {seat['name']}, but let's wait a bit.... ({current_step}/{total_steps})")
        with put_loading():
            time.sleep(15)
            response = requests.get(f"{API_BASE_URL}/v1/pve/find-seat-ip-pve/{seat['name']}")
        if response.status_code == 200:
            seat_ip_proxmox = response.json().get('ip_address')
            if seat_ip_proxmox:
                put_success(f"IP address for seat {seat['name']}: {seat_ip_proxmox}")
            else:
                put_error(f"Failed to find IP for seat {seat['name']}.")
        else:
            put_error(f"Failed to find IP for seat {seat['name']}. Error: {response.text}")

        time.sleep(2)

        # Step 8: Find Guacamole Seat IP
        current_step += 1
        put_info(f"Finding Guacamole IP for seat {seat['name']}, but let's wait a bit.... ({current_step}/{total_steps})")
        with put_loading():
            time.sleep(15)
            response = requests.get(f"{API_BASE_URL}/v1/pve/find-seat-ip/{seat['name']}")
        if response.status_code == 200:
            seat_ip = response.json().get('ip_address')
            if seat_ip:
                put_success(f"IP address for seat {seat['name']}: {seat_ip}")
            else:
                put_error(f"Failed to find IP for seat {seat['name']}.")
        else:
            put_error(f"Failed to find IP for seat {seat['name']}. Error: {response.text}")

        time.sleep(2)

        # Step 9: Create connections for Guacamole User
        current_step += 1
        put_info(f"Creating connections in Guacamole and adding them to {seat['first_name']} {seat['last_name']}... ({current_step}/{total_steps})")

        # Find the matching template in the training templates
        template = next((t for t in training_templates if t["name"] == selected_training), None)

        if template:
            connections = template["connections"]
            for connection in connections:
                connection_name = connection["connection_name"].replace("{{first_name}}", seat["first_name"]).replace("{{last_name}}", seat["last_name"])
                
                # Prepare connection data
                connection_data = {
                    "parentIdentifier": connection.get("parent_id", "ROOT"),
                    "name": connection_name,
                    "protocol": connection["protocol"],
                    "parameters": {},
                    "attributes": {
                        "guacd-hostname": connection["proxy_hostname"].replace("{{guacd_proxy_ip}}", seat_ip),
                        "guacd-port": str(connection["proxy_port"])
                    }
                }

                # Add all parameters from the connection, excluding specific keys
                excluded_keys = ["connection_name", "parent_id", "protocol", "proxy_hostname", "proxy_port"]
                for key, value in connection.items():
                    if key not in excluded_keys:
                        connection_data["parameters"][key] = str(value) if isinstance(value, bool) else value

                # Remove any parameters with empty values
                connection_data["parameters"] = {k: v for k, v in connection_data["parameters"].items() if v != ""}

                with put_loading():
                    try:
                        # Create the connection
                        response = requests.post(f"{API_BASE_URL}/v2/guacamole/connections", json=connection_data)
                        response.raise_for_status()
                        result = response.json()
                        
                        if 'connection_id' in result:
                            connection_id = result['connection_id']
                            
                            # Give permission to the user
                            add_connection_data = {
                                "username": guacamole_username,
                                "connection_id": connection_id
                            }
                            response = requests.post(f"{API_BASE_URL}/v2/guacamole/add-to-connection", json=add_connection_data)
                            response.raise_for_status()
                            
                            put_success(f"Connection {connection_name} created and added to user {guacamole_username} successfully.")
                        else:
                            put_error(f"Failed to create connection {connection_name}. Connection ID not received.")
                    except requests.RequestException as e:
                        put_error(f"Failed to create or assign connection {connection_name}. Error: {str(e)}")
                        
                    put_info(f"Adding user {guacamole_username} to connection group...")
                    try:
                        response = requests.post(f"{API_BASE_URL}/v2/guacamole/add-to-connection-group", json={
                            "username": guacamole_username,
                            "connection_group_id": template["connection_group_id"]
                        })
                        response.raise_for_status()
                        put_success(f"User {guacamole_username} added to connection group successfully.")
                    except requests.RequestException as e:
                        put_error(f"Failed to add user {guacamole_username} to connection group. Error: {str(e)}")

        else:
            put_error(f"No template found for training: {selected_training}")

        time.sleep(2)
        
        # Step 10: Check if VM needs to be shut down
        current_step += 1
        put_info(f"Checking if VM needs to be shut down... ({current_step}/{total_steps})")

        start_date = datetime.strptime(training_dates['start_date'], '%d-%m-%Y').date()
        today = datetime.now().date()

        if start_date > today:
            put_info(f"Start date {start_date} is in the future. Attempting to shut down VM {seat['name']}...")
            try:
                response = requests.post(f"{API_BASE_URL}/v1/pve/shutdown-vm/{seat['name']}")
                response.raise_for_status()
                put_success(f"Shutdown command sent for VM {seat['name']}.")
            except requests.RequestException as e:
                put_error(f"Failed to send shutdown command for VM {seat['name']}. Error: {str(e)}")
        else:
            put_info(f"Start date {start_date} is today or in the past. Keeping VM {seat['name']} running.")

    put_success("Training seats creation process completed!")