from pywebio.input import input, checkbox, input_group, select, textarea
from pywebio.output import put_text, put_error, put_loading, put_info, put_success, clear, put_warning
import requests
from datetime import datetime
import time
import re
import unidecode
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import secrets
import string
import traceback
import logging

# Load environment variables
load_dotenv()

API_BASE_URL = "http://localhost:8081/api"

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_password(length=8):
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

# Email configuration
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')

def sanitize_name(name):
    # Remove leading/trailing whitespace
    name = name.strip()
    
    # Replace multiple spaces with a single space
    name = re.sub(r'\s+', ' ', name)
    
    # Replace umlauts with their two-letter equivalents
    umlaut_map = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        'ß': 'ss'
    }
    for umlaut, replacement in umlaut_map.items():
        name = name.replace(umlaut, replacement)
    
    # Use unidecode to replace any remaining accented characters with their ASCII equivalents
    name = unidecode.unidecode(name)
    
    # Remove any characters that aren't letters, numbers, spaces, or hyphens
    name = re.sub(r'[^a-zA-Z0-9\s-]', '', name)
    
    # Replace spaces with dashes
    name = name.replace(' ', '-')
    
    # Capitalize each part, except for the last part if it contains numbers
    parts = name.split('-')
    for i in range(len(parts)):
        if i == len(parts) - 1 and any(char.isdigit() for char in parts[i]):
            parts[i] = ''.join(char.upper() if char.isalpha() else char for char in parts[i])
        else:
            parts[i] = parts[i].capitalize()
    
    return '-'.join(parts)

def send_deployment_email(ticket_number, deployed_users, proxmox_uris, user_passwords, vm_details, training_dates, student_info, selected_training):
    subject = f"Training Deployment Summary - Ticket {ticket_number}"
    
    body = "Deployment summary:\n\n"
    body += f"Training: {selected_training}\n"
    body += f"Training Start Date: {training_dates['start_date']}\n"
    body += f"Training End Date: {training_dates['end_date']}\n\n"
    
    body += "Student Information:\n"
    for student in student_info:
        body += f"- {student['first_name']} {student['last_name']}\n"
    body += "\n"
    
    body += "Deployed users:\n"
    for user in deployed_users:
        body += f"- {user}\n"
    
    body += "\nProxmox URIs of student seats for trainer:\n"
    for user, uri in proxmox_uris.items():
        body += f"- {user}: {uri}\n"

    body += "\nVM Details:\n"
    for vm_name, details in vm_details.items():
        body += f"- {vm_name}:\n"
        body += f"  IP: {details['ip']}\n"
        body += f"  Node: {details['node']}\n"
        body += f"  VMID: {details['vmid']}\n"

    body += "\nUser Credentials:\n"
    for user, password in user_passwords.items():
        if password == "user has already been created at an earlier date":
            body += f"- {user}: {password}\n"
        else:
            body += f"- {user}: {password}\n"

    msg = MIMEMultipart()
    msg['From'] = SMTP_USERNAME
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.ehlo()  # Can be omitted
        server.starttls()  # Secure the connection
        server.ehlo()  # Can be omitted
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        #clear()
        put_success(f"Deployment summary email for Ticket {ticket_number} sent successfully.\n\nEmail Body:\n{body}")
    except Exception as e:
        put_error(f"Failed to send deployment summary email for Ticket {ticket_number}. Error: {str(e)}")

def create_training_seats():
    try:
        with open("training_templates.json") as file:
            training_templates = json.load(file)
    except FileNotFoundError:
        put_error("training_templates.json file not found.")
        return
    except json.JSONDecodeError:
        put_error("Error decoding training_templates.json. Please check the file format.")
        return
    
    # Get available training options from training_templates.json
    training_options = [template["name"] for template in training_templates]

    # Ask the user to select the desired training
    selected_training = select("Select the training", options=training_options, required=True)

    # Find the selected training template
    selected_template = next((t for t in training_templates if t["name"] == selected_training), None)
    if not selected_template:
        put_error(f"No template found for training: {selected_training}")
        return
    
    dhcp_server_id = selected_template.get("dhcp_server_id")
    if not dhcp_server_id:
        put_error(f"No DHCP server ID found for training: {selected_training}")
        return

    # Request ticket number
    ticket_number = input("Enter the ticket number (format: T20240709.0037)", required=True)

    # Validate ticket number format
    while not re.match(r'^T\d{8}\.\d{4}$', ticket_number):
        put_error("Invalid ticket number format. Please use the format T20240709.0037.")
        ticket_number = input("Enter the ticket number (format: T20240709.0037)", required=True)

    training_dates = input_group("Enter training dates", [
        input("Training Start Date (DD-MM-YYYY)", name="start_date", required=True),
        input("Training End Date (DD-MM-YYYY)", name="end_date", required=True)
    ])
    
    # Get student names
    students_input = textarea("Enter student names (one per line):", rows=10)
    
    # Process the input
    students = [line.strip() for line in students_input.split('\n') if line.strip()]
    
    seats = []
    for student in students:
        # Split the name into first and last name
        name_parts = student.split(maxsplit=1)
        if len(name_parts) < 2:
            put_warning(f"Skipping invalid name: {student}")
            continue
        
        first_name, last_name = name_parts
        
        first_name = sanitize_name(first_name)
        last_name = sanitize_name(last_name)
        
        if first_name and last_name:
            seats.append({
                "first_name": first_name,
                "last_name": last_name,
            })
        else:
            put_warning(f"Skipping invalid name: {student}")

    student_info = [
    {
        "first_name": seat['first_name'],
        "last_name": seat['last_name']
    }
    for seat in seats
    ]
    
    num_seats = len(seats)
    put_info(f"Number of valid seats to create: {num_seats}")

    total_steps = len(seats) * 11  # Adjust the number of steps if needed
    
    current_step = 0
    deployed_users = []
    proxmox_uris = {}
    user_passwords = {}
    vm_details = {}

    for idx, seat in enumerate(seats):
        # Step 1: Find best node for selected date
        current_step += 1
        put_info(f"Finding the best available node for {seat['first_name']} {seat['last_name']} on {training_dates['start_date']}... ({current_step}/{total_steps})")
        with put_loading():
            response = requests.get(f"{API_BASE_URL}/v1/pve/evaluate-nodes-for-date/{training_dates['start_date']}")
        if response.status_code != 200:
            put_error(f"Failed to get the best available node. Error: {response.text}")
            continue

        best_node = response.json().get('best_node')
        if not best_node:
            put_error("No suitable node found for the given date.")
            continue

        put_success(f"Best node selected for {training_dates['start_date']}: {best_node}")

        # Get the template ID for the best node
        template_id = selected_template["template_ids"].get(best_node)
        if not template_id:
            put_error(f"No template ID found for node {best_node}")
            continue

        # Create VM name
        vm_name = f"{seat['first_name']}-{seat['last_name']}-{selected_training}"

        # Step 2: Create VM
        current_step += 1
        put_info(f"Creating VM for {vm_name} on node {best_node}... ({current_step}/{total_steps})")
        with put_loading():
            response = requests.post(f"{API_BASE_URL}/v1/pve/create-linked-clone", json={
                "name": vm_name,
                "template_id": template_id,
                "node": best_node
            })
        if response.status_code != 200:
            put_error(f"Failed to create VM for {vm_name}.")
            continue

        time.sleep(5)

        # Step 3: Adding tags to VM
        current_step += 1
        put_info(f"Adding tags to VM {vm_name}... ({current_step}/{total_steps})")
        tags = [
            f"start-{training_dates['start_date']}",
            f"end-{training_dates['end_date']}"
        ]
        with put_loading():
            response = requests.post(f"{API_BASE_URL}/v1/pve/add-tags-to-vm", json={
                "vm_name": vm_name,
                "tags": tags
            })
        if response.status_code != 200:
            put_error(f"Failed to add tags to VM {vm_name}. Error: {response.text}")

        time.sleep(5)

        # Step 4: Starting VM
        current_step += 1
        put_info(f"Starting VM {vm_name}... ({current_step}/{total_steps})")
        with put_loading():
            response = requests.post(f"{API_BASE_URL}/v1/pve/start-vm/{vm_name}")
        if response.status_code != 200:
            put_error(f"Failed to start VM {vm_name}. Error: {response.text}")

        time.sleep(5)

        # Step 5: Check if user exists in Authentik and create if not
        current_step += 1
        put_info(f"Checking/Creating Authentik user for {seat['first_name']} {seat['last_name']}... ({current_step}/{total_steps})")

        username = f"{seat['first_name'].lower()}.{seat['last_name'].lower()}"
        email = f"{username}@infinigate-labs.com"

        authentik_user_data = {
            "username": username,
            "email": email,
            "name": f"{seat['first_name']} {seat['last_name']}",
            "password": generate_password()
        }

        with put_loading():
            create_response = requests.post(f"{API_BASE_URL}/v1/authentik/users", json=authentik_user_data)

        response_json = create_response.json()

        #put_info(f"Response status: {create_response.status_code}")
        #put_info(f"Response content: {create_response.text}")

        if "message" in response_json and "already exists" in response_json["message"]:
            put_warning(f"User {username} already exists in Authentik. Skipping creation.")
            user_passwords[username] = "user has already been created at an earlier date"
        elif create_response.status_code == 200:
            put_success(f"Authentik user {username} created successfully.")
            user_passwords[username] = authentik_user_data["password"]
        else:
            error_message = response_json.get("message", create_response.text)
            put_error(f"Failed to create Authentik user for {username}. Error: {error_message}")
            user_passwords[username] = "Failed to create user"

        time.sleep(5)

        # Step 6: Create User in Guacamole
        current_step += 1
        put_info(f"Creating Guacamole user for {seat['first_name']} {seat['last_name']}... ({current_step}/{total_steps})")
        guacamole_username = f"{seat['first_name'].lower()}.{seat['last_name'].lower()}@infinigate-labs.com"
        try:
            with put_loading():
                response = requests.post(f"{API_BASE_URL}/v1/guacamole/users/{guacamole_username}")
            if response.status_code != 200:
                put_error(f"Failed to create Guacamole user for {vm_name}. Error: {response.text}")
            else:
                put_success(f"Guacamole user created for {guacamole_username}")
        except Exception as e:
            put_error(f"An error occurred during Guacamole user creation: {str(e)}")

        time.sleep(2)

        # Step 7: Find Proxmox Seat IP
        current_step += 1
        put_info(f"Finding Proxmox IP for seat {vm_name}, but let's wait a bit.... ({current_step}/{total_steps})")
        try:
            with put_loading():
                time.sleep(30)
                response = requests.get(f"{API_BASE_URL}/v1/pve/find-seat-ip-pve/{vm_name}")
            if response.status_code == 200:
                seat_info = response.json()
                if 'ip_address' in seat_info and isinstance(seat_info['ip_address'], dict):
                    ip_info = seat_info['ip_address']
                    seat_ip_proxmox = ip_info.get('ip_address')
                    node = ip_info.get('node')
                    vmid = ip_info.get('vmid')
                    
                    # Store VM details
                    vm_name = f"{seat['first_name']}-{seat['last_name']}-{selected_training}"
                    vm_details[vm_name] = {
                        "ip": seat_ip_proxmox,
                        "node": node,
                        "vmid": vmid
                    }

                    success_message = f"IP address for seat {vm_name}: {seat_ip_proxmox}"
                    if node and vmid:
                        success_message += f" (Node: {node}, VMID: {vmid})"
                    put_success(success_message)
                else:
                    put_error(f"Failed to find IP for seat {vm_name}.")
            else:
                put_error(f"Failed to find IP for seat {vm_name}. Error: {response.text}")
        except Exception as e:
            put_error(f"An error occurred while finding Proxmox IP: {str(e)}")

        # Step 8: Create connections for Guacamole User
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
                        "guacd-hostname": connection["proxy_hostname"].replace("{{guacd_proxy_ip}}", seat_ip_proxmox),
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

        # After creating the user
        deployed_users.append(f"{seat['first_name'].lower()}.{seat['last_name'].lower()}")
        proxmox_uris[f"{seat['first_name'].lower()}.{seat['last_name'].lower()}"] = f"https://proxmox-{seat['first_name'].lower()}-{seat['last_name'].lower()}.student-access.infinigate-labs.com"
        
        # Step 9: Check if VM needs to be shut down
        current_step += 1
        put_info(f"Checking if VM needs to be shut down... ({current_step}/{total_steps})")

        start_date = datetime.strptime(training_dates['start_date'], '%d-%m-%Y').date()
        today = datetime.now().date()

        vm_name = f"{seat['first_name']}-{seat['last_name']}-{selected_training}"

        if start_date > today:
            put_info(f"Start date {start_date} is in the future. Attempting to shut down VM {vm_name}...")
            try:
                response = requests.post(f"{API_BASE_URL}/v1/pve/shutdown-vm/{vm_name}")
                response.raise_for_status()
                put_success(f"Shutdown command sent for VM {vm_name}.")
            except requests.RequestException as e:
                put_error(f"Failed to send shutdown command for VM {vm_name}. Error: {str(e)}")
        else:
            put_info(f"Start date {start_date} is today or in the past. Keeping VM {vm_name} running.")
            
        # Step 10: Get VM MAC address
        current_step += 1
        put_info(f"Getting MAC address for VM {vm_name}... ({current_step}/{total_steps})")
        try:
            with put_loading():
                response = requests.get(f"{API_BASE_URL}/v1/pve/get-vm-mac-address/{vm_name}")
            if response.status_code == 200:
                mac_address = response.json()['mac_address']
                vm_details[vm_name]['mac_address'] = mac_address
                put_success(f"MAC address for VM {vm_name}: {mac_address}")
            else:
                put_error(f"Failed to get MAC address for VM {vm_name}. Error: {response.text}")
        except Exception as e:
            put_error(f"An error occurred while getting MAC address: {str(e)}")
            
        # Step 11: Create DHCP reservation
        current_step += 1
        put_info(f"Creating DHCP reservation for VM {vm_name}... ({current_step}/{total_steps})")
        try:
            with put_loading():
                mac_address = vm_details[vm_name]['mac_address']
                seat_name = f"{seat['first_name'].lower()}.{seat['last_name'].lower()}"
                
                # Make a request to the FastAPI endpoint to create DHCP reservation
                response = requests.post(f"{API_BASE_URL}/api/v1/fortigate/add-dhcp-reservation", 
                    json={
                        "mac": mac_address,
                        "seat": seat_name,
                        "dhcp_server_id": dhcp_server_id
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    assigned_ip = result["assigned_ip"]
                    vm_details[vm_name]['dhcp_ip'] = assigned_ip
                    put_success(f"DHCP reservation created for VM {vm_name}: {assigned_ip}")
                else:
                    error_detail = response.json().get("detail", "Unknown error")
                    put_error(f"Failed to create DHCP reservation for VM {vm_name}. Error: {error_detail}")
        except Exception as e:
            put_error(f"An error occurred while creating DHCP reservation: {str(e)}")
            logger.error(f"Error creating DHCP reservation for VM {vm_name}: {str(e)}")
            logger.error(traceback.format_exc())

        # Add a small delay to allow for DHCP reservation to propagate
        time.sleep(2)

        # Validate the DHCP reservation
        try:
            with put_loading():
                validate_response = requests.get(f"{API_BASE_URL}/api/v1/fortigate/validate-dhcp/{seat_name}/{dhcp_server_id}")
                
                if validate_response.status_code == 200:
                    validated_ip = validate_response.json()["assigned_ip"]
                    if validated_ip == assigned_ip:
                        put_success(f"DHCP reservation for VM {vm_name} validated successfully: {validated_ip}")
                    else:
                        put_warning(f"DHCP reservation for VM {vm_name} has a mismatch. Assigned: {assigned_ip}, Validated: {validated_ip}")
                else:
                    put_warning(f"Failed to validate DHCP reservation for VM {vm_name}")
        except Exception as e:
            put_error(f"An error occurred while validating DHCP reservation: {str(e)}")
            logger.error(f"Error validating DHCP reservation for VM {vm_name}: {str(e)}")
            logger.error(traceback.format_exc())

    put_success("Training seats creation process completed!")

    send_deployment_email(
    ticket_number,
    deployed_users,
    proxmox_uris,
    user_passwords,
    vm_details,
    training_dates,
    student_info,
    selected_training
    )

if __name__ == "__main__":
    create_training_seats()
