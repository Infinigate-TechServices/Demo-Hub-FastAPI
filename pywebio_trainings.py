from pywebio.input import input, checkbox, input_group, NUMBER
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
        clear()  # Clear previous messages
        put_error("Failed to retrieve templates.")
        return

    clear()  # Clear previous messages
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
            
            if first_name and last_name:  # Ensure names are not empty after sanitization
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

    total_steps = len(seats) * 3
    current_step = 0
    for idx, seat in enumerate(seats):
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

        current_step += 1
        put_info(f"Starting VM {seat['name']}... ({current_step}/{total_steps})")
        with put_loading():
            response = requests.post(f"{API_BASE_URL}/v1/pve/start-vm/{seat['name']}")
        if response.status_code != 200:
            put_error(f"Failed to start VM {seat['name']}. Error: {response.text}")
        
        time.sleep(5)

    put_success("Training seats creation and startup process completed!")