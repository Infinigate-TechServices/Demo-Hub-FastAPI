from pywebio.input import input, checkbox, input_group, NUMBER, select
from pywebio.output import put_text, put_error, put_loading, put_info, put_success, clear
import requests
from datetime import datetime
import time
import re
import unidecode

API_BASE_URL = "http://localhost:8081/api"

def sanitize_name(name):
    # Remove leading/trailing whitespace
    name = name.strip()
    
    # Replace multiple spaces with a single space
    name = re.sub(r'\s+', ' ', name)
    
    # Remove any characters that aren't letters, spaces, or hyphens
    name = re.sub(r'[^a-zA-Z\s-]', '', name)
    
    # Replace umlauts and other diacritical marks
    name = unidecode.unidecode(name)
    
    # Replace spaces with dashes
    name = name.replace(' ', '-')
    
    # Capitalize each word (now separated by dashes)
    name = '-'.join(word.capitalize() for word in name.split('-'))
    
    return name

def create_training_seats():
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
    selected_template = checkbox("Select a template for the training seats", options=template_options, required=True)[0]
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

    total_steps = len(seats) * 7  # Adjust the number of steps if needed
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

        # Step 4: Create User in LLDAP
        current_step += 1
        put_info(f"Creating LLDAP user for {seat['first_name']} {seat['last_name']}... ({current_step}/{total_steps})")
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

        # Step 5: Add user to group in LLDAP
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

        # Step 6: Create User in Guacamole
        current_step += 1
        put_info(f"Creating Guacamole user for {seat['first_name']} {seat['last_name']}... ({current_step}/{total_steps})")
        guacamole_username = f"{seat['first_name'].lower()}.{seat['last_name'].lower()}@infinigate-labs.com"
        with put_loading():
            response = requests.post(f"{API_BASE_URL}/v1/guacamole/users/{guacamole_username}")
        if response.status_code != 200:
            put_error(f"Failed to create Guacamole user for {seat['name']}. Error: {response.text}")

        # Step 7: Find Seat IP
        current_step += 1
        put_info(f"Finding IP for seat {seat['name']}, but let's wait.... ({current_step}/{total_steps})")
        with put_loading():
            time.sleep(30)
            response = requests.get(f"{API_BASE_URL}/v1/pve/find-seat-ip/{seat['name']}")
        if response.status_code == 200:
            seat_ip = response.json().get('ip_address')
            if seat_ip:
                put_success(f"IP address for seat {seat['name']}: {seat_ip}")
            else:
                put_error(f"Failed to find IP for seat {seat['name']}.")
        else:
            put_error(f"Failed to find IP for seat {seat['name']}. Error: {response.text}")

        # Step 5: Add connections to Guacamole
        # This step would typically involve creating RDP or SSH connections in Guacamole
        # You'll need to implement the necessary API endpoint and adjust this code accordingly
        # put_info(f"Adding Guacamole connections for {seat['name']}... ({current_step}/{total_steps})")
        # with put_loading():
        #     response = requests.post(f"{API_BASE_URL}/v1/guacamole/connections", json={
        #         "username": guacamole_username,
        #         "ip_address": seat_ip,
        #         "protocol": "rdp",  # or "ssh", depending on your needs
        #     })
        # if response.status_code != 200:
        #     put_error(f"Failed to add Guacamole connections for {seat['name']}. Error: {response.text}")

    put_success("Training seats creation process completed!")