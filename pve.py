from proxmoxer import ProxmoxAPI
from proxmoxer.backends import https
from models import TrainingSeat, VM, AddTagsRequest
import os
import sys
from dotenv import load_dotenv
import time
import threading
import json
import logging
from datetime import datetime, date, timedelta
import schedule
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

# Get Proxmox connection details from environment variables
proxmox_host = os.getenv('PVE_HOST')
proxmox_token_id = os.getenv('PVE_TOKEN_ID')
proxmox_token_secret = os.getenv('PVE_TOKEN_SECRET')
proxmox_port = int(os.getenv('PVE_PORT', 443))

# Initialize the Proxmox API client
proxmox = None

def authenticate_proxmox():
    global proxmox
    
    # Split the token ID into user and token_name
    user, token_name = proxmox_token_id.rsplit('!', 1)
    
    proxmox = ProxmoxAPI(
        proxmox_host,
        user=user,
        token_name=token_name,
        token_value=proxmox_token_secret,
        port=proxmox_port,
        verify_ssl=False
    )
    print("Authenticated with Proxmox using API token")

# Authenticate initially
authenticate_proxmox()

# Function to refresh the authentication ticket periodically
def refresh_ticket():
    while True:
        time.sleep(7200 - 600)  # Sleep for 1 hour and 50 minutes
        try:
            authenticate_proxmox()
            print("Proxmox API ticket refreshed")
        except Exception as e:
            print(f"Failed to refresh Proxmox API ticket: {e}")

# Start the ticket refresh thread
ticket_refresh_thread = threading.Thread(target=refresh_ticket)
ticket_refresh_thread.daemon = True
ticket_refresh_thread.start()

# Dynamically get all PVE_NODE variables from .env
proxmox_nodes = []
index = 1
while True:
    node = os.getenv(f'PVE_NODE{index}')
    if node:
        proxmox_nodes.append(node)
    else:
        break
    index += 1

vms_scheduled_for_deletion = {}  # Format: {vm_name: {'id': vmid, 'end_date': date_obj, 'deletion_date': date_obj}}
deletion_lock = threading.Lock()

def parse_date_from_tag(tag):
    """Parse date from tag string in format 'end-DD-MM-YYYY'"""
    try:
        date_str = tag[4:]  # Remove 'end-' prefix
        return datetime.strptime(date_str, '%d-%m-%Y').date()
    except ValueError:
        return None

def update_vm_schedule(vm_name: str, vm_id: int, end_date: date) -> bool:
    """
    Updates or adds a VM to the deletion schedule without attempting to delete it.
    Only sets or updates the deletion_date based on the end_date.
    
    Args:
        vm_name: Name of the VM
        vm_id: ID of the VM
        end_date: The end date from the VM's tag
        
    Returns:
        bool: True if schedule was updated, False if there was an error
    """
    try:
        deletion_date = end_date + timedelta(days=3)
        
        with deletion_lock:
            if vm_name in vms_scheduled_for_deletion:
                current_end_date = vms_scheduled_for_deletion[vm_name]['end_date']
                if current_end_date != end_date:
                    logger.info(f"Updating deletion schedule for VM {vm_name} due to end date change "
                              f"(Old: {current_end_date.strftime('%d-%m-%Y')}, "
                              f"New: {end_date.strftime('%d-%m-%Y')})")
            else:
                logger.info(f"Adding VM {vm_name} to deletion schedule")
            
            vms_scheduled_for_deletion[vm_name] = {
                'id': vm_id,
                'end_date': end_date,
                'deletion_date': deletion_date
            }
            
            logger.info(f"VM {vm_name} (ID: {vm_id}) scheduled - End date: {end_date.strftime('%d-%m-%Y')}, "
                       f"Deletion date: {deletion_date.strftime('%d-%m-%Y')}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating deletion schedule for VM {vm_name}: {str(e)}")
        return False

def update_all_vm_schedules():
    """
    Check all VMs for end tags and update their deletion schedules.
    Only handles schedule updates, no deletions.
    """
    logger.info("Starting VM schedule update process")
    today = date.today()
    logger.info(f"Checking VMs for date: {today.strftime('%d-%m-%Y')}")
    
    valid_vms = set()
    updated_schedules = []
    removed_schedules = []
    
    # Scan all VMs across all nodes
    for node in proxmox.nodes.get():
        logger.info(f"Checking node: {node['node']}")
        for vm in proxmox.nodes(node['node']).qemu.get():
            logger.info(f"Checking VM: {vm['name']} (ID: {vm['vmid']})")
            valid_vms.add(vm['name'])
            
            if 'tags' in vm and vm['tags']:
                tags = vm['tags'].split(';')
                logger.info(f"VM {vm['name']} has tags: {tags}")
                
                # Look for end date tag
                end_date = None
                for tag in tags:
                    tag = tag.strip()
                    if tag.startswith('end-'):
                        end_date = parse_date_from_tag(tag)
                
                # Update or remove from schedule based on end date
                if end_date:
                    if update_vm_schedule(vm['name'], vm['vmid'], end_date):
                        updated_schedules.append({
                            'vm_name': vm['name'],
                            'vm_id': vm['vmid'],
                            'end_date': end_date.strftime('%d-%m-%Y'),
                            'deletion_date': (end_date + timedelta(days=3)).strftime('%d-%m-%Y')
                        })
                elif vm['name'] in vms_scheduled_for_deletion:
                    with deletion_lock:
                        logger.info(f"Removing {vm['name']} from deletion schedule as end tag was removed")
                        removed_schedules.append(vm['name'])
                        del vms_scheduled_for_deletion[vm['name']]
    
    # Clean up non-existent VMs
    with deletion_lock:
        scheduled_vms = list(vms_scheduled_for_deletion.keys())
        for vm_name in scheduled_vms:
            if vm_name not in valid_vms:
                logger.info(f"Removing {vm_name} from deletion schedule as it no longer exists")
                removed_schedules.append(vm_name)
                del vms_scheduled_for_deletion[vm_name]
    
    logger.info(f"Schedule update completed: {len(updated_schedules)} updated, "
           f"{len(removed_schedules)} removed, "
           f"{len(vms_scheduled_for_deletion)} total scheduled")
    
    return {
        "updated": updated_schedules,
        "removed": removed_schedules,
        "total_scheduled": len(vms_scheduled_for_deletion)
    }

def check_scheduled_deletions():
    """Check for and process VMs scheduled for deletion today or in the past."""
    logger.info("Checking scheduled deletions")
    today = date.today()
    to_delete = []
    
    with deletion_lock:
        for vm_name, info in vms_scheduled_for_deletion.items():
            if info['deletion_date'] <= today:
                logger.info(f"VM {vm_name} marked for deletion (Deletion date {info['deletion_date'].strftime('%d-%m-%Y')} "
                          f"has passed or is today)")
                to_delete.append((vm_name, info['id']))
            else:
                days_until_deletion = (info['deletion_date'] - today).days
                logger.info(f"VM {vm_name} scheduled for deletion in {days_until_deletion} days "
                           f"(End date: {info['end_date'].strftime('%d-%m-%Y')}, "
                           f"Deletion date: {info['deletion_date'].strftime('%d-%m-%Y')})")
    
    if to_delete:
        logger.info(f"Found {len(to_delete)} VMs to delete")
    else:
        logger.info("No VMs need to be deleted at this time")
    
    # Process deletions
    for vm_name, vm_id in to_delete:
        logger.info(f"Processing deletion for VM {vm_name} (ID: {vm_id})")
        result = remove_vm(VM(name=vm_name, template_id=None))
        
        if "has been stopped and removed" in result:
            logger.info(f"Successfully removed VM {vm_name} (ID: {vm_id})")
            with deletion_lock:
                if vm_name in vms_scheduled_for_deletion:
                    del vms_scheduled_for_deletion[vm_name]
        else:
            logger.error(f"Failed to remove VM {vm_name} (ID: {vm_id}). Result: {result}")

def get_scheduled_deletions():
    """Get the current list of scheduled deletions."""
    with deletion_lock:
        return {
            vm_name: {
                'id': info['id'],
                'end_date': info['end_date'].strftime('%d-%m-%Y'),
                'deletion_date': info['deletion_date'].strftime('%d-%m-%Y')
            }
            for vm_name, info in vms_scheduled_for_deletion.items()
        }

def clear_scheduled_deletions():
    """Clear all scheduled deletions without removing VMs."""
    logger.info("Clearing all scheduled deletions")
    
    with deletion_lock:
        cleared_entries = {
            vm_name: {
                'id': info['id'],
                'end_date': info['end_date'].strftime('%d-%m-%Y'),
                'deletion_date': info['deletion_date'].strftime('%d-%m-%Y')
            }
            for vm_name, info in vms_scheduled_for_deletion.items()
        }
        count = len(vms_scheduled_for_deletion)
        vms_scheduled_for_deletion.clear()
        
        logger.info(f"Cleared {count} entries from scheduled deletions")
        
    return {
        "message": f"Successfully cleared {count} scheduled deletions",
        "cleared_count": count,
        "cleared_entries": cleared_entries
    }

def check_vm_start_status():
    """
    Check VMs for start tags and start them if:
    - The start date is today or in the past
    - The VM is not already running
    
    Returns:
        dict: Information about started VMs and attempts
    """
    logger.info("Starting VM start status check")
    today = date.today()
    started_vms = []
    already_running = []
    failed_starts = []

    for node in proxmox.nodes.get():
        logger.info(f"Checking node: {node['node']}")
        for vm in proxmox.nodes(node['node']).qemu.get():
            if 'tags' in vm and vm['tags']:
                tags = vm['tags'].split(';')
                logger.debug(f"Checking start tags for VM {vm['name']}")
                
                # Look for start date tag
                for tag in tags:
                    tag = tag.strip()
                    if tag.startswith('start-'):
                        try:
                            start_date = datetime.strptime(tag[6:], '%d-%m-%Y').date()
                            if start_date <= today:
                                # Check if VM is already running
                                status = proxmox.nodes(node['node']).qemu(vm['vmid']).status.current.get()
                                
                                if status['status'] == 'running':
                                    logger.info(f"VM {vm['name']} already running")
                                    already_running.append(vm['name'])
                                else:
                                    logger.info(f"Starting VM {vm['name']} (ID: {vm['vmid']}) as start date "
                                              f"{start_date.strftime('%d-%m-%Y')} has passed")
                                    result = start_vm(vm['name'])
                                    
                                    if "error" not in result:
                                        started_vms.append({
                                            'name': vm['name'],
                                            'id': vm['vmid'],
                                            'start_date': start_date.strftime('%d-%m-%Y')
                                        })
                                    else:
                                        failed_starts.append({
                                            'name': vm['name'],
                                            'id': vm['vmid'],
                                            'error': result['error']
                                        })
                        except ValueError:
                            logger.error(f"Invalid date format in start tag for VM {vm['name']}: {tag}")

    return {
        "started": started_vms,
        "already_running": already_running,
        "failed": failed_starts
    }

def schedule_daily_check():
    """Schedule the daily background tasks."""
    # Update schedules at 3:00 AM
    schedule.every().day.at("03:00").do(run_schedule_update)
    # Check VMs to start at 3:30 AM
    schedule.every().day.at("03:30").do(run_start_check)
    # Process deletions at 4:00 AM
    schedule.every().day.at("04:00").do(run_deletion_check)
    
    logger.info("Daily tasks scheduled: "
                "schedule update at 3:00 AM, "
                "VM start check at 3:30 AM, "
                "deletion check at 4:00 AM")

    while True:
        schedule.run_pending()
        time.sleep(60)  # Sleep for 1 minute

def run_schedule_update():
    """Run the schedule update process."""
    logger.info("Running VM schedule update process")
    try:
        update_all_vm_schedules()
        logger.info("Completed VM schedule update process")
    except Exception as e:
        logger.error(f"Error in VM schedule update process: {e}")

def run_deletion_check():
    """Run the deletion check process."""
    logger.info("Running VM deletion check process")
    try:
        check_scheduled_deletions()
        logger.info("Completed VM deletion check process")
    except Exception as e:
        logger.error(f"Error in VM deletion check process: {e}")

def run_start_check():
    """Run the VM start check process."""
    logger.info("Running VM start check process")
    try:
        result = check_vm_start_status()
        logger.info(f"VM start check completed: "
                   f"{len(result['started'])} VMs started, "
                   f"{len(result['already_running'])} already running, "
                   f"{len(result['failed'])} failed to start")
    except Exception as e:
        logger.error(f"Error in VM start check process: {e}")

def run_check_now():
    """Run all checks immediately."""
    logger.info("Running immediate VM check processes")
    try:
        # First update schedules
        update_all_vm_schedules()
        # Then check VM starts
        check_vm_start_status()
        # Finally check for deletions
        check_scheduled_deletions()
        logger.info("Completed immediate VM check processes")
    except Exception as e:
        logger.error(f"Error during immediate checks: {e}")

def start_background_check():
    logger.info("Starting background check scheduler")
    background_check_thread = threading.Thread(target=schedule_daily_check)
    background_check_thread.daemon = True
    background_check_thread.start()
    logger.info("Background VM check scheduler started")

def evaluate_nodes():
    best_node = None
    max_memory = 0
    max_disk = 0

    for node in proxmox_nodes:
        status = proxmox.nodes(node).status().get()
        free_memory = status['memory']['free']
        free_disk = status['rootfs']['free']

        if free_memory > max_memory and free_disk > max_disk:
            max_memory = free_memory
            max_disk = free_disk
            best_node = node

    return best_node

def evaluate_nodes_for_date(target_date):
    target_date = datetime.strptime(target_date, "%d-%m-%Y").date()
    best_node = None
    min_expected_load_ratio = float('inf')

    for node in proxmox_nodes:
        node_status = proxmox.nodes(node).status.get()
        total_memory = node_status['memory']['total']
        
        expected_memory_usage = 0
        vms = proxmox.nodes(node).qemu.get()
        
        for vm in vms:
            vm_config = proxmox.nodes(node).qemu(vm['vmid']).config.get()
            max_memory = int(vm_config.get('memory', 0))
            if 'balloon' in vm_config:
                max_memory = max(max_memory, int(vm_config['balloon']))
            
            if 'tags' in vm and vm['tags']:
                tags = vm['tags'].split(';')
                for tag in tags:
                    if tag.startswith('start-'):
                        start_date_str = tag[6:]
                        try:
                            start_date = datetime.strptime(start_date_str, "%d-%m-%Y").date()
                            if start_date <= target_date:
                                expected_memory_usage += max_memory
                                break
                        except ValueError:
                            logger.warning(f"Invalid date format in tag for VM {vm['name']}: {tag}")
        
        # Calculate the expected load ratio
        expected_load_ratio = expected_memory_usage / total_memory
        
        logger.info(f"Node {node}: Expected memory usage: {expected_memory_usage / (1024*1024):.2f} GB, "
                    f"Total memory: {total_memory / (1024*1024):.2f} GB, "
                    f"Expected load ratio: {expected_load_ratio:.2f}")
        
        if expected_load_ratio < min_expected_load_ratio:
            min_expected_load_ratio = expected_load_ratio
            best_node = node

    if best_node:
        logger.info(f"Selected best node for {target_date}: {best_node} "
                    f"with expected load ratio: {min_expected_load_ratio:.2f}")
    else:
        logger.warning(f"No suitable node found for date {target_date}")

    return best_node

def create_training_seat(name: str, template_id: int):
    best_node = evaluate_nodes()
    if not best_node:
        return {"error": "No suitable node found"}

    vmid = proxmox.cluster.nextid.get()
    return proxmox.nodes(best_node).qemu(template_id).post('clone', vmid=template_id, newid=vmid, name=name, full=1)

def remove_training_seat(seat: TrainingSeat):
    for node in proxmox_nodes:
        vms = proxmox.nodes(node).qemu().get()
        for vm in vms:
            if vm['name'] == seat.name:
                vmid = vm['vmid']
                return proxmox.nodes(node).qemu(vmid).delete()
    return {"error": "VM not found"}

def create_linked_clone(name: str, template_id: int, node: str):
    if not node:
        return {"error": "No node specified"}
    
    vmid = proxmox.cluster.nextid.get()
    return proxmox.nodes(node).qemu(template_id).post('clone', vmid=template_id, newid=vmid, name=name, full=0)

def remove_all_scheduled_vms():
    """Immediately remove all VMs that are scheduled for deletion."""
    logger.info("Starting immediate removal of all VMs scheduled for deletion")
    removed_vms = []
    failed_removals = []

    with deletion_lock:
        scheduled_vms = list(vms_scheduled_for_deletion.items())

    for vm_name, info in scheduled_vms:
        logger.info(f"Attempting to remove VM {vm_name} (ID: {info['id']}) immediately")
        vmid, node = get_vm_id_and_node(vm_name)
        
        if vmid is None or node is None:
            logger.warning(f"VM '{vm_name}' not found. It may have been already removed.")
            removed_vms.append(vm_name)
            with deletion_lock:
                if vm_name in vms_scheduled_for_deletion:
                    del vms_scheduled_for_deletion[vm_name]
            continue

        result = remove_vm(VM(name=vm_name, template_id=None))
        
        if "has been stopped and removed" in result:
            logger.info(f"Successfully removed VM {vm_name} (ID: {info['id']})")
            removed_vms.append(vm_name)
            with deletion_lock:
                if vm_name in vms_scheduled_for_deletion:
                    del vms_scheduled_for_deletion[vm_name]
        else:
            logger.error(f"Failed to remove VM {vm_name} (ID: {info['id']}). Result: {result}")
            failed_removals.append(vm_name)

    total_scheduled = len(scheduled_vms)
    total_removed = len(removed_vms)
    total_failed = len(failed_removals)

    logger.info(f"Removal process completed. "
                f"Total scheduled: {total_scheduled}, "
                f"Successfully removed: {total_removed}, "
                f"Failed removals: {total_failed}")

    return {
        "message": f"Removal process completed. {total_removed} VMs removed, {total_failed} failed.",
        "removed_vms": removed_vms,
        "failed_removals": failed_removals
    }

def clear_scheduled_deletions():
    """Clear all scheduled deletions without removing VMs."""
    logger.info("Clearing all scheduled deletions")
    
    with deletion_lock:
        cleared_entries = {
            vm_name: {
                'id': info['id'],
                'end_date': info['end_date'].strftime('%d-%m-%Y'),
                'deletion_date': info['deletion_date'].strftime('%d-%m-%Y')
            }
            for vm_name, info in vms_scheduled_for_deletion.items()
        }
        count = len(vms_scheduled_for_deletion)
        vms_scheduled_for_deletion.clear()
        
        logger.info(f"Cleared {count} entries from scheduled deletions")
        
    return {
        "message": f"Successfully cleared {count} scheduled deletions",
        "cleared_count": count,
        "cleared_entries": cleared_entries
    }

def remove_vm(vm: VM):
    logger.info(f"Attempting to remove VM '{vm.name}'")
    
    vmid, node = get_vm_id_and_node(vm.name)
    if vmid is None or node is None:
        logger.warning(f"VM '{vm.name}' not found for removal.")
        return f"VM '{vm.name}' not found on any node."

    logger.info(f"Found VM '{vm.name}' (ID: {vmid}) on node {node}")
    
    try:
        if stop_vm(vm.name):
            timeout = 60
            start_time = time.time()
            while time.time() - start_time < timeout:
                status = proxmox.nodes(node).qemu(vmid).status.current.get()['status']
                if status == 'stopped':
                    proxmox.nodes(node).qemu(vmid).delete()
                    logger.info(f"VM '{vm.name}' (ID: {vmid}) has been stopped and removed from node {node}.")
                    return f"VM '{vm.name}' with ID {vmid} has been stopped and removed from node {node}."
                time.sleep(1)
            
            logger.error(f"Timeout waiting for VM '{vm.name}' (ID: {vmid}) to stop on node {node}")
            return f"Timeout waiting for VM '{vm.name}' to stop on node {node}. Please check its status manually."
        else:
            logger.error(f"Failed to stop VM '{vm.name}' (ID: {vmid}) on node {node}")
            return f"Failed to stop VM '{vm.name}' on node {node}. Cannot proceed with removal."
    except Exception as e:
        logger.error(f"Error processing VM '{vm.name}' on node {node}: {str(e)}")
        return f"Error removing VM '{vm.name}' on node {node}: {str(e)}"

def list_vms():
    vms_list = []
    for node in proxmox_nodes:
        vms = proxmox.nodes(node).qemu().get()
        vms_list.extend(vms)
    return sorted(vms_list, key=lambda x: x.get('name', ''))

def get_vm_id(vm_name):
    logger.debug(f"Searching for VM with name: {vm_name}")
    for node in proxmox.nodes.get():
        logger.debug(f"Checking node: {node['node']}")
        for vm in proxmox.nodes(node['node']).qemu.get():
            logger.debug(f"Found VM: {vm['name']} (ID: {vm['vmid']})")
            if vm['name'] == vm_name:
                logger.info(f"VM found: {vm_name} (ID: {vm['vmid']})")
                return vm['vmid']
    logger.warning(f"VM not found: {vm_name}")
    return None

def get_vm_id_and_node(vm_name):
    logger.debug(f"Searching for VM with name: {vm_name}")
    for node in proxmox.nodes.get():
        logger.debug(f"Checking node: {node['node']}")
        for vm in proxmox.nodes(node['node']).qemu.get():
            logger.debug(f"Found VM: {vm['name']} (ID: {vm['vmid']})")
            if vm['name'] == vm_name:
                logger.info(f"VM found: {vm_name} (ID: {vm['vmid']}) on node {node['node']}")
                return vm['vmid'], node['node']
    logger.warning(f"VM not found: {vm_name}")
    return None, None

def find_seat_ip(vm_name: str) -> str:
    for node in proxmox.nodes.get():
        for vm in proxmox.nodes(node['node']).qemu.get():
            if vm['name'] == vm_name:
                try:
                    command = "pct exec 200 -- bash -c \"ip -4 addr show eth0 | grep -oP '(?<=inet\\s)\\d+(\\.\\d+){3}'\""
                    result = proxmox.nodes(node['node']).qemu(vm['vmid']).agent.exec.post(command=command)
                    
                    pid = result['pid']
                    
                    for _ in range(30):  # Try for 30 seconds
                        time.sleep(1)
                        status = proxmox.nodes(node['node']).qemu(vm['vmid']).agent('exec-status').get(pid=pid)
                        if status['exited']:
                            if 'out-data' in status:
                                return status['out-data'].strip()
                            break
                except Exception as e:
                    print(f"Error processing VM {vm_name}: {str(e)}")
    return None

def find_seat_ip_pve(vm_name: str) -> dict:
    for node in proxmox.nodes.get():
        node_name = node['node']
        for vm in proxmox.nodes(node_name).qemu.get():
            if vm['name'] == vm_name:
                try:
                    interfaces_data = proxmox.nodes(node_name).qemu(vm['vmid']).agent.get('network-get-interfaces')
                    for interface in interfaces_data.get('result', []):
                        if 'ip-addresses' in interface:
                            for ip_addr in interface['ip-addresses']:
                                if ip_addr['ip-address-type'] == 'ipv4' and ip_addr['ip-address'].startswith('100.64.'):
                                    return {
                                        "ip_address": ip_addr['ip-address'],
                                        "node": node_name,
                                        "vmid": vm['vmid']
                                    }
                except Exception as e:
                    print(f"Error processing VM {vm_name} on node {node_name}: {str(e)}")
    return None

def add_tags_to_vm(request: AddTagsRequest):
    logger.info(f"Attempting to add tags to VM: {request.vm_name}")
    logger.debug(f"Tags to add: {request.tags}")
    
    tags_string = ','.join(request.tags)
    logger.debug(f"Tags string: {tags_string}")
    
    vmid, node = get_vm_id_and_node(request.vm_name)
    if vmid is None or node is None:
        logger.warning(f"VM with name {request.vm_name} not found")
        return False
    
    try:
        logger.debug(f"Updating tags for VM {request.vm_name} (ID: {vmid}) on node {node}")
        logger.debug(f"Proxmox API call: proxmox.nodes('{node}').qemu({vmid}).config.put(tags='{tags_string}')")
        proxmox.nodes(node).qemu(vmid).config.put(tags=tags_string)
        logger.info(f"Tags updated successfully for VM {request.vm_name}")
        return True
    except Exception as e:
        logger.error(f"Error adding tags to VM {request.vm_name} on node {node}: {str(e)}")
        return False
    
def start_vm(vm_name: str):
    logger.info(f"Attempting to start VM: {vm_name}")
    vmid, node = get_vm_id_and_node(vm_name)
    if vmid is None or node is None:
        logger.error(f"VM '{vm_name}' not found")
        return {"error": f"VM '{vm_name}' not found"}
    
    try:
        logger.info(f"Attempting to start VM '{vm_name}' (ID: {vmid}) on node {node}")
        result = proxmox.nodes(node).qemu(vmid).status.start.post()
        logger.info(f"Start command sent for VM '{vm_name}'. Result: {result}")
        return {"message": f"VM '{vm_name}' start command sent successfully"}
    except Exception as e:
        logger.error(f"Error starting VM '{vm_name}' on node {node}: {str(e)}")
        return {"error": f"VM '{vm_name}' could not be started. Error: {str(e)}"}

def stop_vm(vm_name: str) -> bool:
    vmid, node = get_vm_id_and_node(vm_name)
    if vmid is None or node is None:
        logger.warning(f"Cannot stop VM '{vm_name}': VM not found")
        return False
    
    try:
        proxmox.nodes(node).qemu(vmid).status.stop.post()
        logger.info(f"VM '{vm_name}' (ID: {vmid}) stop command sent on node {node}")
        return True
    except Exception as e:
        logger.error(f"Failed to stop VM '{vm_name}' (ID: {vmid}) on node {node}: {str(e)}")
        return False

def shutdown_vm(vm_name: str):
    vmid, node = get_vm_id_and_node(vm_name)
    if vmid is None or node is None:
        logger.warning(f"VM '{vm_name}' not found for shutdown.")
        return {"error": f"VM '{vm_name}' not found."}

    logger.info(f"Attempting to shut down VM '{vm_name}' (ID: {vmid}) on node {node}")
    
    try:
        proxmox.nodes(node).qemu(vmid).status.shutdown.post()
        logger.info(f"Shutdown command sent for VM '{vm_name}' (ID: {vmid}) on node {node}")
        return {"message": f"Shutdown command sent for VM '{vm_name}' with ID {vmid} on node {node}."}
    except Exception as e:
        logger.error(f"Error shutting down VM '{vm_name}' (ID: {vmid}) on node {node}: {str(e)}")
        return {"error": f"Failed to shut down VM '{vm_name}'. Error: {str(e)}"}

def get_vm_mac_address(vm_name):
    vmid, node = get_vm_id_and_node(vm_name)
    if vmid is None or node is None:
        logger.warning(f"Cannot get MAC address: VM '{vm_name}' not found")
        return None

    try:
        vm_config = proxmox.nodes(node).qemu(vmid).config.get()
        # Assuming the first network interface is the one we want
        net0 = vm_config.get('net0')
        if net0:
            # Extract MAC address from the net0 string
            mac = net0.split(',')[0].split('=')[1]
            logger.info(f"MAC address for VM '{vm_name}' (ID: {vmid}) on node {node}: {mac}")
            return mac
        else:
            logger.warning(f"No network interface found for VM '{vm_name}' (ID: {vmid}) on node {node}")
            return None
    except Exception as e:
        logger.error(f"Error getting MAC address for VM '{vm_name}' (ID: {vmid}) on node {node}: {str(e)}")
        return None

# Start the background check thread
start_background_check()
