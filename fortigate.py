import requests
import time
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from dotenv import load_dotenv
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

FGT_ADDR = os.getenv('FGT_ADDR')
API_KEY = os.getenv('FGT_API_KEY')

headers = {
    'accept': 'application/json',
    'Content-Type': 'application/json'
}

params = {
    'access_token': API_KEY,
    'vdom': 'training'
}

def get_dhcp_server_config(dhcp_server_id):
    logger.info(f"Getting DHCP server configuration for server ID: {dhcp_server_id}")
    url = f"{FGT_ADDR}/api/v2/cmdb/system.dhcp/server/{dhcp_server_id}"
    response = requests.get(url, headers=headers, params=params, verify=False)
    if response.status_code == 200:
        return response.json().get('results', [{}])[0]
    else:
        logger.error(f"Failed to get DHCP server configuration. Status code: {response.status_code}")
        return None

def add_dhcp_reservation(mac, seat, dhcp_server_id):
    logger.info(f"Adding DHCP reservation for MAC: {mac}, Seat: {seat}, DHCP Server ID: {dhcp_server_id}")
    
    # Get current DHCP server configuration
    dhcp_config = get_dhcp_server_config(dhcp_server_id)
    if not dhcp_config:
        return None

    # Extract IP range information
    ip_ranges = dhcp_config.get('ip-range', [])
    if not ip_ranges:
        logger.error("No IP ranges found in DHCP server configuration")
        return None

    # Use the first IP range (you might want to implement more sophisticated logic here)
    start_ip = ip_ranges[0].get('start-ip')
    end_ip = ip_ranges[0].get('end-ip')

    # Find the next available IP
    reserved_addresses = dhcp_config.get('reserved-address', [])
    reserved_ips = set(addr['ip'] for addr in reserved_addresses)
    
    next_ip = find_next_available_ip(start_ip, end_ip, reserved_ips)
    if not next_ip:
        logger.error("No available IP addresses in the DHCP range")
        return None

    # Prepare the new reservation
    new_lease = {
        "ip": next_ip,
        "mac": mac,
        "action": "reserved",
        "description": seat
    }
    reserved_addresses.append(new_lease)

    # Update DHCP server configuration
    update_data = {
        "reserved-address": reserved_addresses
    }

    url = f"{FGT_ADDR}/api/v2/cmdb/system.dhcp/server/{dhcp_server_id}"
    response = requests.put(url, headers=headers, params=params, json=update_data, verify=False)
    
    if response.status_code == 200:
        logger.info(f"DHCP reservation added successfully for {seat}: {next_ip}")
        return next_ip
    else:
        logger.error(f"Failed to add DHCP reservation. Status code: {response.status_code}")
        return None

def find_next_available_ip(start_ip, end_ip, reserved_ips):
    start = ip_to_int(start_ip)
    end = ip_to_int(end_ip)
    for ip in range(start, end + 1):
        candidate = int_to_ip(ip)
        if candidate not in reserved_ips:
            return candidate
    return None

def ip_to_int(ip):
    return int(''.join([bin(int(x)+256)[3:] for x in ip.split('.')]), 2)

def int_to_ip(x):
    return '.'.join([str(x >> (i << 3) & 0xFF) for i in range(4)[::-1]])

def remove_dhcp_reservations(seat_macs, dhcp_server_id):
    logger.info(f"Removing DHCP reservations for MACs: {seat_macs}, DHCP Server ID: {dhcp_server_id}")
    
    # Get current DHCP server configuration
    dhcp_config = get_dhcp_server_config(dhcp_server_id)
    if not dhcp_config:
        return 0

    reserved_addresses = dhcp_config.get('reserved-address', [])
    updated_reservations = [r for r in reserved_addresses if r['mac'] not in seat_macs]
    removed_count = len(reserved_addresses) - len(updated_reservations)

    update_data = {
        "reserved-address": updated_reservations
    }

    url = f"{FGT_ADDR}/api/v2/cmdb/system.dhcp/server/{dhcp_server_id}"
    response = requests.put(url, headers=headers, params=params, json=update_data, verify=False)
    
    if response.status_code == 200:
        logger.info(f"Removed {removed_count} DHCP reservations")
        return removed_count
    else:
        logger.error(f"Failed to remove DHCP reservations. Status code: {response.status_code}")
        return 0

def validate_dhcp_by_name(seat, dhcp_server_id):
    logger.info(f"Validating DHCP reservation for seat: {seat}")
    
    dhcp_config = get_dhcp_server_config(dhcp_server_id)
    if not dhcp_config:
        return None

    reserved_addresses = dhcp_config.get('reserved-address', [])
    for reservation in reserved_addresses:
        if reservation.get('description') == seat:
            logger.info(f"Validated DHCP reservation for {seat}: {reservation['ip']}")
            return reservation['ip']

    logger.warning(f"No DHCP reservation found for seat: {seat}")
    return None