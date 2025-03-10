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
from urllib.parse import quote

# Load environment variables
load_dotenv()

API_BASE_URL = "http://localhost:8081/api"

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_password(length=12):
    """
    Generate a password avoiding confusing characters like l, I, 1, O, 0.
    Returns a string of the specified length (default 12) containing unambiguous characters.
    """
    letters_clear = ''.join(c for c in string.ascii_letters if c not in 'lIoO')
    digits_clear = ''.join(c for c in string.digits if c not in '01')
    alphabet = letters_clear + digits_clear
    
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        has_letter = any(c.isalpha() for c in password)
        has_number = any(c.isdigit() for c in password)
        
        if has_letter and has_number:
            return password

# Email configuration
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USERNAME = os.getenv('SMTP_USERNAME')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')

def prepare_connection_data(connection, connection_group_id, seat_ip_proxmox, seat):
    """
    Prepare connection data handling both proxy and direct connections.
    Ensures output matches GuacamoleConnectionRequest model.
    """
    # Prepare the name with replaced placeholders
    name = connection["connection_name"].replace("{{first_name}}", seat["first_name"]).replace("{{last_name}}", seat["last_name"])
    
    # Initialize parameters and attributes dictionaries
    parameters = {}
    attributes = {}

    # Add all parameters from the connection
    excluded_keys = ["connection_name", "protocol", "proxy_hostname", "proxy_port", "direct_connection", "parent_id"]
    for key, value in connection.items():
        if key not in excluded_keys:
            if key == "hostname" and value == "{{guacd_proxy_ip}}":
                parameters[key] = seat_ip_proxmox
            else:
                # Convert to string as Guacamole expects all parameters as strings
                parameters[key] = str(value) if value is not None else ""

    # Add proxy settings only if this is not a direct connection
    if not connection.get("direct_connection", False):
        if "proxy_hostname" in connection and "proxy_port" in connection:
            attributes["guacd-hostname"] = connection["proxy_hostname"].replace("{{guacd_proxy_ip}}", seat_ip_proxmox)
            attributes["guacd-port"] = str(connection["proxy_port"])

    # Construct the final connection data matching the GuacamoleConnectionRequest model
    connection_data = {
        "parentIdentifier": str(connection_group_id),  # Ensure this is a string
        "name": name,
        "protocol": connection["protocol"],
        "parameters": parameters,
        "attributes": attributes if attributes else {}  # Always include attributes, even if empty
    }

    return connection_data

def sanitize_training_name(name):
    # Remove any characters that aren't alphanumeric, spaces, or hyphens
    sanitized = re.sub(r'[^a-zA-Z0-9\s-]', '', name)
    # Replace spaces with hyphens
    sanitized = sanitized.replace(' ', '-')
    # Convert to lowercase
    sanitized = sanitized.lower()
    # Remove any leading or trailing hyphens
    sanitized = sanitized.strip('-')
    # Limit the length to 63 characters (Proxmox VM name limit)
    sanitized = sanitized[:63]
    return sanitized

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
    
    # Split into parts
    parts = name.split('-')
    for i in range(len(parts)):
        # Just capitalize the first letter of each part, regardless of numbers
        if parts[i]:
            parts[i] = parts[i][0].upper() + parts[i][1:].lower()
    
    return '-'.join(parts)

def validate_and_format_date(date_str):
    """
    Validates date format and converts dots to dashes if necessary.
    Returns formatted date string if valid, None if invalid.
    """
    # First, replace any dots with dashes
    date_str = date_str.replace('.', '-')
    
    # Check if the date matches the required format (DD-MM-YYYY)
    if not re.match(r'^(0[1-9]|[12][0-9]|3[01])-(0[1-9]|1[0-2])-\d{4}$', date_str):
        return None
        
    try:
        # Verify it's a valid date
        datetime.strptime(date_str, '%d-%m-%Y')
        return date_str
    except ValueError:
        return None

def send_deployment_email(ticket_number, deployed_users, proxmox_uris, user_passwords, vm_details, training_dates, student_info, selected_training):
    subject = f"Training Deployment Summary - Ticket {ticket_number}"
    
    # Calculate total number of seats
    total_seats = len(student_info)
    
    body = "Deployment summary:\n\n"
    body += f"Training: {selected_training}\n"
    body += f"Training Start Date: {training_dates['start_date']}\n"
    body += f"Training End Date: {training_dates['end_date']}\n\n"
    
    body += f"URL for student connections: https://student-access.infinigate-labs.com\n"

    body += f"\nSeats deployed in total: {total_seats}\n"
    body += "\nStudent Credentials:\n"
    for user, password in user_passwords.items():
        if password == "user has already been created at an earlier date":
            body += f"{user}: {password}\n"
        else:
            body += f"{user}: {password}\n"

    body += "\nIMPORTANT NOTE: Direct access to the Proxmox UI via proxy hosts is currently disabled.\n"
    body += "\nProxmox URIs of student seats for trainer:\n"
    for user, uri in proxmox_uris.items():
        body += f"{user}: {uri}\n"

    body += "\nVM Details:\n"
    for vm_name, details in vm_details.items():
        body += f"{vm_name}:\n"
        body += f"  IP: {details['ip']}\n"
        body += f"  Node: {details['node']}\n"
        body += f"  VM ID: {details['vmid']}\n"
        body += f"  MAC Address: {details.get('mac_address', 'N/A')}\n\n"

    body += "Student Information:\n"
    for student in student_info:
        body += f"{student['first_name']} {student['last_name']}\n"
    body += "\n"

    msg = MIMEMultipart()
    msg['From'] = SMTP_USERNAME
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
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
    training_options = []
    for template in training_templates:
        training_options.extend(template["name"])

    # Ask the user to select the desired training
    selected_training = select("Select the training", options=training_options, required=True)

    # Find the selected training template
    selected_template = next((t for t in training_templates if selected_training in t["name"]), None)
    if not selected_template:
        put_error(f"No template found for training: {selected_training}")
        return
    
    dhcp_server_id = selected_template.get("dhcp_server_id")
    if not dhcp_server_id:
        put_error(f"No DHCP server ID found for training: {selected_training}")
        return

    # Sanitize the selected training name
    sanitized_training_name = sanitize_training_name(selected_training)

    # Request ticket number with validation
    ticket_number = input("Enter the ticket number (format: T20240709.0037)", required=True)
    while not re.match(r'^T\d{8}\.\d{4}$', ticket_number):
        put_error("Invalid ticket number format. Please use the format T20240709.0037.")
        ticket_number = input("Enter the ticket number (format: T20240709.0037)", required=True)

    # Request and validate training dates
    while True:
        training_dates = input_group("Enter training dates (format: DD-MM-YYYY)", [
            input("Training Start Date", name="start_date", required=True),
            input("Training End Date", name="end_date", required=True)
        ])
        
        # Validate and format start date
        formatted_start_date = validate_and_format_date(training_dates['start_date'])
        formatted_end_date = validate_and_format_date(training_dates['end_date'])
        
        if not formatted_start_date:
            put_error("Invalid start date format. Please use DD-MM-YYYY format (e.g., 24-10-2024)")
            continue
            
        if not formatted_end_date:
            put_error("Invalid end date format. Please use DD-MM-YYYY format (e.g., 24-10-2024)")
            continue
            
        # Verify end date is not before start date
        start_date = datetime.strptime(formatted_start_date, '%d-%m-%Y')
        end_date = datetime.strptime(formatted_end_date, '%d-%m-%Y')
        
        if end_date < start_date:
            put_error("End date cannot be before start date.")
            continue
            
        # If we get here, both dates are valid
        training_dates['start_date'] = formatted_start_date
        training_dates['end_date'] = formatted_end_date
        break
    
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

    total_steps = len(seats) * 12  # Adjust the number of steps if needed
    
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

        # Create VM name using the sanitized training name
        vm_name = f"{seat['first_name']}-{seat['last_name']}-{sanitized_training_name}"

        # Ensure the entire vm_name is not longer than 63 characters
        if len(vm_name) > 63:
            # If it's too long, truncate the sanitized_training_name part
            max_training_name_length = 63 - len(f"{seat['first_name']}-{seat['last_name']}-") - 1  # -1 for extra hyphen
            vm_name = f"{seat['first_name']}-{seat['last_name']}-{sanitized_training_name[:max_training_name_length]}"

        # Ensure the vm_name doesn't end with a hyphen
        vm_name = vm_name.rstrip('-')

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

        # Step 5: Check if user exists in Authentik, create if not, and add to "Trainingsteilnehmer" group
        current_step += 1
        put_info(f"Checking/Creating Authentik user for {seat['first_name']} {seat['last_name']} and adding to group... ({current_step}/{total_steps})")

        username = f"{seat['first_name'].lower()}.{seat['last_name'].lower()}"
        email = f"{username}@infinigate-labs.com"

        authentik_user_data = {
            "username": username,
            "email": email,
            "name": f"{seat['first_name']} {seat['last_name']}",
            "password": generate_password()
        }

        # Create or check user
        put_text("Creating/Checking Authentik user...")
        with put_loading():
            create_response = requests.post(f"{API_BASE_URL}/v1/authentik/users", json=authentik_user_data)
            response_json = create_response.json()

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
            put_info("Skipping to next user...")
            continue  # Skip to next iteration if user creation failed

        # Get user ID
        put_text("Getting user ID...")
        with put_loading():
            user_id_response = requests.get(f"{API_BASE_URL}/v1/authentik/users/{username}")
        if user_id_response.status_code == 200:
            user_id = user_id_response.json()["user_id"]
            put_info(f"User ID retrieved for {username}")
        else:
            put_error(f"Failed to get user ID for {username}. Error: {user_id_response.text}")
            put_info("Skipping to next user...")
            continue  # Skip to next iteration if we couldn't get the user ID

        # Get group ID for "Trainingsteilnehmer"
        put_text("Getting group ID...")
        with put_loading():
            group_id_response = requests.get(f"{API_BASE_URL}/v1/authentik/groups/Trainingsteilnehmer")
        if group_id_response.status_code == 200:
            group_id = group_id_response.json()["group_id"]
            put_info("Group ID retrieved for Trainingsteilnehmer")
        else:
            put_error(f"Failed to get group ID for Trainingsteilnehmer. Error: {group_id_response.text}")
            put_info("Skipping to next user...")
            continue  # Skip to next iteration if we couldn't get the group ID

        # Add user to group
        put_text("Adding user to group...")
        with put_loading():
            add_to_group_response = requests.post(f"{API_BASE_URL}/v1/authentik/add-user-to-group", json={
                "user_id": user_id,
                "group_id": group_id
            })
        if add_to_group_response.status_code == 200:
            put_success(f"User {username} added to Trainingsteilnehmer group successfully.")
        else:
            put_error(f"Failed to add user {username} to Trainingsteilnehmer group. Error: {add_to_group_response.text}")

        put_info("Waiting 5 seconds before proceeding...")
        time.sleep(5)

        # Step 6: Check if user exists in Guacamole, create if not
        current_step += 1
        put_info(f"Checking if Guacamole user exists for {seat['first_name']} {seat['last_name']}... ({current_step}/{total_steps})")
        guacamole_username = f"{seat['first_name'].lower()}.{seat['last_name'].lower()}@infinigate-labs.com"

        try:
            with put_loading():
                logging.debug(f"Attempting to fetch users from: {API_BASE_URL}/v1/guacamole/list-users")
                response = requests.get(f"{API_BASE_URL}/v1/guacamole/list-users")
                logging.debug(f"Response status code: {response.status_code}")
                logging.debug(f"Response content: {response.text[:1000]}...")  # Log first 1000 characters

            if response.status_code == 200:
                try:
                    response_data = response.json()
                    users = response_data.get('users', {})
                    
                    user_exists = guacamole_username in users
                    
                    if user_exists:
                        put_warning(f"Guacamole user {guacamole_username} already exists. Skipping creation.")
                    else:
                        put_info(f"Creating Guacamole user for {guacamole_username}...")
                        create_response = requests.post(f"{API_BASE_URL}/v1/guacamole/users/{guacamole_username}")
                        if create_response.status_code == 200:
                            put_success(f"Guacamole user created for {guacamole_username}")
                        else:
                            put_error(f"Failed to create Guacamole user for {guacamole_username}. Error: {create_response.text}")
                except json.JSONDecodeError:
                    logging.error("Failed to parse JSON response")
                    put_error("Failed to parse response from Guacamole API")
            else:
                put_error(f"Failed to retrieve Guacamole users. Status code: {response.status_code}, Error: {response.text}")
        except Exception as e:
            logging.exception("An error occurred during Guacamole user check/creation")
            put_error(f"An error occurred during Guacamole user check/creation: {str(e)}")

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
                    
                    # Store VM details using the correct, sanitized vm_name
                    vm_details[vm_name] = {
                        "ip": seat_ip_proxmox,
                        "node": node,
                        "vmid": vmid,
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

        # Step 8: Create connection group, create connections, and add them to Guacamole User
        current_step += 1
        put_info(f"Creating connections in Guacamole and adding them to {seat['first_name']} {seat['last_name']}... ({current_step}/{total_steps})")

        if selected_template:
            # Create connection group name using sanitized training name and start date
            connection_group_name = f"{sanitized_training_name}-{training_dates['start_date']}"
            
            try:
                # First check if connection group exists
                response = requests.get(f"{API_BASE_URL}/v1/guacamole/connection-groups")
                response.raise_for_status()
                groups = response.json().get("connection_groups", {})
                
                connection_group_id = None
                for group_id, group in groups.items():
                    if group.get("name") == connection_group_name and group.get("parentIdentifier") == "ROOT":
                        connection_group_id = group.get("identifier")
                        put_info(f"Found existing connection group: {connection_group_name} (ID: {connection_group_id})")
                        break
                
                # Create group only if it doesn't exist
                if not connection_group_id:
                    connection_group_data = {
                        "name": connection_group_name,
                        "parent_identifier": "ROOT",
                        "type": "ORGANIZATIONAL"
                    }
                    response = requests.post(f"{API_BASE_URL}/v1/guacamole/connection-groups", json=connection_group_data)
                    response.raise_for_status()
                    
                    # Get the new group's identifier
                    time.sleep(2)
                    response = requests.get(f"{API_BASE_URL}/v1/guacamole/connection-groups")
                    response.raise_for_status()
                    groups = response.json().get("connection_groups", {})
                    
                    for group_id, group in groups.items():
                        if group.get("name") == connection_group_name and group.get("parentIdentifier") == "ROOT":
                            connection_group_id = group.get("identifier")
                            put_success(f"Created new connection group: {connection_group_name} (ID: {connection_group_id})")
                            break
                
                if not connection_group_id:
                    raise Exception(f"Could not find or create connection group: {connection_group_name}")
                
                put_success(f"Created connection group: {connection_group_name} (ID: {connection_group_id})")
                
                # Create connections within the new connection group
                connections = selected_template["connections"]
                for connection in connections:
                    try:
                        # Use the new prepare_connection_data function
                        connection_data = prepare_connection_data(
                            connection=connection,
                            connection_group_id=connection_group_id,
                            seat_ip_proxmox=seat_ip_proxmox,
                            seat=seat
                        )
                        
                        # Create connection
                        response = requests.post(f"{API_BASE_URL}/v2/guacamole/connections", json=connection_data)
                        response.raise_for_status()
                        result = response.json()
                        
                        if 'connection_id' in result:
                            connection_id = result['connection_id']
                            
                            # Add connection permission
                            add_connection_data = {
                                "username": guacamole_username,
                                "connection_id": connection_id
                            }
                            response = requests.post(f"{API_BASE_URL}/v2/guacamole/add-to-connection", json=add_connection_data)
                            response.raise_for_status()
                            
                            put_success(f"Connection {connection_data['name']} created and added to user {guacamole_username}")
                        else:
                            put_error(f"Failed to create connection {connection_data['name']}")
                    except requests.RequestException as e:
                        put_error(f"Failed to create or assign connection {connection_data['name']}: {str(e)}")
                
                # Add user to connection group
                try:
                    response = requests.post(f"{API_BASE_URL}/v2/guacamole/add-to-connection-group", json={
                        "username": guacamole_username,
                        "connection_group_id": connection_group_id
                    })
                    response.raise_for_status()
                    put_success(f"User {guacamole_username} added to connection group {connection_group_name}")
                except requests.RequestException as e:
                    put_error(f"Failed to add user to connection group: {str(e)}")
                            
            except Exception as e:
                put_error(f"An error occurred while creating connection group and connections: {str(e)}")
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
                mac_address = vm_details[vm_name].get('mac_address')
                if not mac_address:
                    put_error(f"MAC address not found for VM {vm_name}")
                    continue  # Skip to the next iteration of the loop

                seat_name = f"{seat['first_name'].lower()}.{seat['last_name'].lower()}"
                ip_address = vm_details[vm_name]['ip']  # Use the IP address we got from Proxmox
                
                # Make a request to the new FastAPI endpoint to create DHCP reservation with known IP
                response = requests.post(f"{API_BASE_URL}/v1/fortigate/add-dhcp-reservation-known-ip", 
                    json={
                        "mac": mac_address,
                        "seat": seat_name,
                        "ip": ip_address,
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
                validate_response = requests.get(f"{API_BASE_URL}/v1/fortigate/validate-dhcp/{seat_name}/{dhcp_server_id}")
                
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
            
        current_step += 1
        put_info(f"Step 12 (Nginx Reverse Proxy) is currently disabled... ({current_step}/{total_steps})")
        """
        put_info(f"Creating or Updating Reverse Proxy Entry for {vm_name}... ({current_step}/{total_steps})")
        try:
            domain_name = f"proxmox-{seat['first_name'].lower()}-{seat['last_name'].lower()}.student-access.infinigate-labs.com"
            proxy_host_data = {
                "domain_names": [domain_name],
                "forward_scheme": "https",
                "forward_host": seat_ip_proxmox,
                "forward_port": 8006,
                "access_list_id": 0,
                "certificate_id": 13,
                "ssl_forced": 1,
                "caching_enabled": 0,
                "block_exploits": 1,
                "advanced_config": "",
                "allow_websocket_upgrade": 1,
                "http2_support": 1,
                "hsts_enabled": 0,
                "hsts_subdomains": 0,
                "enabled": 1,
                "locations": [],
                "meta": {}
            }

            # Check for existing proxy host
            existing_proxy_hosts_response = requests.get(f"{API_BASE_URL}/v1/nginx/list-proxy-hosts")
            if existing_proxy_hosts_response.status_code == 200:
                existing_proxy_hosts = existing_proxy_hosts_response.json().get("proxy_hosts", [])
                existing_proxy_host = next((host for host in existing_proxy_hosts if domain_name in host.get("domain_names", [])), None)

                if existing_proxy_host:
                    put_warning(f"Existing proxy host found for {domain_name}. Removing...")
                    proxy_host_id = existing_proxy_host['id']
                    delete_response = requests.delete(f"{API_BASE_URL}/v1/nginx/proxy-hosts/{proxy_host_id}")
                    if delete_response.status_code != 200:
                        put_error(f"Failed to delete existing proxy host. Error: {delete_response.text}")
                        raise Exception("Failed to delete existing proxy host")
                    put_success(f"Existing proxy host removed for {domain_name}")

                # Create new proxy host
                with put_loading():
                    create_response = requests.post(f"{API_BASE_URL}/v1/nginx/create-proxy-host", json=proxy_host_data)
                if create_response.status_code == 200:
                    result = create_response.json()
                    proxy_host_id = result.get("proxy_host_id")
                    put_success(f"Reverse Proxy Entry created for {vm_name}. Proxy Host ID: {proxy_host_id}")
                else:
                    put_error(f"Failed to create Reverse Proxy Entry for {vm_name}. Error: {create_response.text}")
                    raise Exception("Failed to create new proxy host")

                # Update the proxmox_uris dictionary with the new domain
                proxmox_uris[f"{seat['first_name'].lower()}.{seat['last_name'].lower()}"] = f"https://{domain_name}"
            else:
                put_error(f"Failed to retrieve existing proxy hosts. Status code: {existing_proxy_hosts_response.status_code}")
                raise Exception("Failed to retrieve existing proxy hosts")

        except Exception as e:
            put_error(f"An error occurred while creating/updating Reverse Proxy Entry: {str(e)}")

        time.sleep(2)
        """
        
        # Still update the proxmox_uris dictionary with the standard format
        domain_name = f"proxmox-{seat['first_name'].lower()}-{seat['last_name'].lower()}.student-access.infinigate-labs.com"
        proxmox_uris[f"{seat['first_name'].lower()}.{seat['last_name'].lower()}"] = f"https://{domain_name}"

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