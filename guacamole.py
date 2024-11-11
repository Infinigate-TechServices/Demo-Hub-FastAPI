import requests
import urllib.parse
import logging
import os
import time
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class Guac:
    def __init__(self, url=None):
        if not url:
            url = os.getenv('GUACAMOLE_URL')
        self.url = url
        self.token = None
        self.headers = {'Accept': 'application/json'}
        self.token_expiry = None
        self.token_lifetime = 60 * 60  # Assume 1 hour token lifetime, adjust as needed
        self.auth(os.getenv('GUACAMOLE_USERNAME'), os.getenv('GUACAMOLE_PASSWORD'))

    def urljoin(self, base, url, allow_fragments=True):
        return urllib.parse.urljoin(base, url, allow_fragments)

    def urlescape(self, url):
        return urllib.parse.quote_plus(url)

    def auth(self, username, password):
        form = {'username': username, 'password': password}
        url = self.urljoin(self.url, 'api/tokens')
        r = requests.post(url, data=form, headers=self.headers)
        d = r.json()
        self.token = d['authToken']
        self.authuser = d['username']
        self.dataSource = d['dataSource']
        self.availableDataSources = d['availableDataSources']
        self.token_expiry = time.time() + self.token_lifetime
        return self.token

    def is_token_valid(self):
        return self.token and time.time() < self.token_expiry

    def refresh_token(self):
        if not self.is_token_valid():
            self.auth(os.getenv('GUACAMOLE_USERNAME'), os.getenv('GUACAMOLE_PASSWORD'))

    def api_request(self, method, endpoint, **kwargs):
        self.refresh_token()
        url = self.urljoin(self.url, endpoint)
        kwargs.setdefault('params', {})['token'] = self.token
        kwargs.setdefault('headers', {}).update(self.headers)
        
        response = requests.request(method, url, **kwargs)
        
        if response.status_code == 401:  # Unauthorized
            self.refresh_token()
            kwargs['params']['token'] = self.token
            response = requests.request(method, url, **kwargs)
        
        return response

    def create_user(self, username):
        data = {
            "username": username,
            "password": self.generate_password(),
            "attributes": {
                "disabled": "",
                "expired": "",
                "access-window-start": "",
                "access-window-end": "",
                "valid-from": "",
                "valid-until": "",
                "timezone": None,
            }
        }
        r = self.api_request('POST', f'api/session/data/{self.dataSource}/users', json=data)
        if r.status_code == 200:
            log.info(f"User {username} created successfully")
            return True
        else:
            log.error(f"Failed to create user {username}: {r.text}")
            return False

    def remove_user(self, username):
        r = self.api_request('DELETE', f'api/session/data/{self.dataSource}/users/{self.urlescape(username)}')
        if r.status_code == 204:
            log.info(f"User {username} removed successfully")
            return True
        else:
            log.error(f"Failed to remove user {username}: {r.text}")
            return False

    def list_users(self):
        r = self.api_request('GET', f'api/session/data/{self.dataSource}/users')
        if r.status_code == 200:
            log.info("Retrieved user list successfully")
            return r.json()
        else:
            log.error(f"Failed to retrieve user list: {r.text}")
            return None

    def generate_password(self, length=16):
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits + string.punctuation
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def newConnection(self, data):
        r = self.api_request('POST', f'api/session/data/{self.dataSource}/connections', json=data)
        return r.json()

    def givePermissionToConnection(self, username, connectionID):
        data = [{
            "op": "add",
            "path": f"/connectionPermissions/{connectionID}",
            "value": "READ"
        }]
        r = self.api_request('PATCH', f'api/session/data/{self.dataSource}/users/{self.urlescape(username)}/permissions', json=data)
        if r.status_code == 204:
            return True
        return False
    
    def add_user_to_connection_group(self, username, connection_group_id):
        data = [{
            "op": "add",
            "path": f"/connectionGroupPermissions/{connection_group_id}",
            "value": "READ"
        }]
        r = self.api_request('PATCH', f'api/session/data/{self.dataSource}/users/{self.urlescape(username)}/permissions', json=data)
        if r.status_code == 204:
            return True
        return False
    
    def list_connection_groups(self):
        """
        List all connection groups in Guacamole.
        
        Returns:
            dict: Dictionary of connection groups and their details
        """
        r = self.api_request('GET', f'api/session/data/{self.dataSource}/connectionGroups')
        if r.status_code == 200:
            log.info("Retrieved connection groups list successfully")
            return r.json()
        else:
            log.error(f"Failed to retrieve connection groups list: {r.text}")
            return None

    def create_connection_group(self, name, parent_identifier="ROOT", type="ORGANIZATIONAL"):
        """
        Create a new connection group in Guacamole.
        
        Args:
            name (str): Name of the connection group
            parent_identifier (str): Identifier of the parent group (default: "ROOT")
            type (str): Type of connection group (default: "ORGANIZATIONAL")
        
        Returns:
            dict: Details of the created connection group if successful, None otherwise
        """
        data = {
            "parentIdentifier": parent_identifier,
            "name": name,
            "type": type,
            "attributes": {
                "max-connections": "",
                "max-connections-per-user": "",
                "enable-session-affinity": ""
            }
        }
        
        try:
            r = self.api_request(
                'POST', 
                f'api/session/data/{self.dataSource}/connectionGroups', 
                json=data
            )
            
            if r.status_code == 200:
                log.info(f"Connection group '{name}' created successfully")
                return r.json()
            else:
                log.error(f"Failed to create connection group. Status code: {r.status_code}, Response: {r.text}")
                return None
        except Exception as e:
            log.error(f"Exception creating connection group: {str(e)}")
            return None
        
    def get_connections_in_group(self, group_identifier):
        """
        Get all connections in a connection group.
        
        Args:
            group_identifier (str): The identifier of the connection group
            
        Returns:
            dict: Dictionary of connections in the group
        """
        try:
            r = self.api_request('GET', f'api/session/data/{self.dataSource}/connections')
            if r.status_code == 200:
                connections = r.json()
                # Filter connections that belong to this group
                group_connections = {
                    conn_id: conn for conn_id, conn in connections.items()
                    if conn.get('parentIdentifier') == group_identifier
                }
                log.info(f"Found {len(group_connections)} connections in group {group_identifier}")
                return group_connections
            else:
                log.error(f"Failed to get connections. Status code: {r.status_code}, Response: {r.text}")
                return None
        except Exception as e:
            log.error(f"Exception getting connections: {str(e)}")
        return None

    def delete_connection(self, connection_identifier):
        """
        Delete a single connection.
        
        Args:
            connection_identifier (str): The identifier of the connection to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            r = self.api_request(
                'DELETE',
                f'api/session/data/{self.dataSource}/connections/{connection_identifier}'
            )
            success = r.status_code == 204  # Guacamole returns 204 on successful deletion
            if success:
                log.info(f"Successfully deleted connection {connection_identifier}")
            else:
                log.error(f"Failed to delete connection {connection_identifier}. Status: {r.status_code}")
            return success
        except Exception as e:
            log.error(f"Exception deleting connection {connection_identifier}: {str(e)}")
            return False

    def get_subgroups(self, group_identifier):
        """
        Get all subgroups within a connection group.
        
        Args:
            group_identifier (str): The identifier of the parent group
            
        Returns:
            dict: Dictionary of subgroups
        """
        try:
            r = self.api_request('GET', f'api/session/data/{self.dataSource}/connectionGroups')
            if r.status_code == 200:
                groups = r.json()
                # Filter groups that are children of this group
                subgroups = {
                    group_id: group for group_id, group in groups.items()
                    if group.get('parentIdentifier') == group_identifier
                }
                log.info(f"Found {len(subgroups)} subgroups in group {group_identifier}")
                return subgroups
            else:
                log.error(f"Failed to get subgroups. Status code: {r.status_code}, Response: {r.text}")
                return None
        except Exception as e:
            log.error(f"Exception getting subgroups: {str(e)}")
            return None

    def delete_connection_group_recursive(self, group_identifier):
        """
        Recursively delete a connection group and all its contents.
        
        Args:
            group_identifier (str): The identifier of the group to delete
            
        Returns:
            dict: Summary of deletion operation
        """
        summary = {
            'connections_deleted': 0,
            'subgroups_deleted': 0,
            'errors': []
        }
        
        try:
            # First, get and delete all connections in this group
            connections = self.get_connections_in_group(group_identifier)
            if connections:
                for conn_id in connections:
                    if self.delete_connection(conn_id):
                        summary['connections_deleted'] += 1
                    else:
                        summary['errors'].append(f"Failed to delete connection {conn_id}")
            
            # Then, recursively delete all subgroups
            subgroups = self.get_subgroups(group_identifier)
            if subgroups:
                for subgroup_id in subgroups:
                    subsummary = self.delete_connection_group_recursive(subgroup_id)
                    summary['connections_deleted'] += subsummary['connections_deleted']
                    summary['subgroups_deleted'] += subsummary['subgroups_deleted'] + 1
                    summary['errors'].extend(subsummary['errors'])
            
            # Finally, delete the group itself
            r = self.api_request(
                'DELETE',
                f'api/session/data/{self.dataSource}/connectionGroups/{group_identifier}'
            )
            
            if r.status_code != 204:  # Guacamole returns 204 on successful deletion
                error_msg = f"Failed to delete group {group_identifier}. Status: {r.status_code}"
                summary['errors'].append(error_msg)
                log.error(error_msg)
            else:
                log.info(f"Successfully deleted group {group_identifier}")
            
            return summary
        
        except Exception as e:
            error_msg = f"Exception during recursive deletion of group {group_identifier}: {str(e)}"
            summary['errors'].append(error_msg)
            log.error(error_msg)
            return summary

    def get_connection_group_by_name(self, group_name):
        """
        Find a connection group by its name.

        Args:
            group_name (str): The name of the connection group to find
            
        Returns:
            dict: Connection group details if found, None otherwise
        """
        try:
            r = self.api_request('GET', f'api/session/data/{self.dataSource}/connectionGroups')
            if r.status_code == 200:
                groups = r.json()
                # Find the group with matching name
                for group_id, group in groups.items():
                    if group.get('name') == group_name:
                        log.info(f"Found group '{group_name}' with ID {group_id}")
                        return group
                log.warning(f"No group found with name '{group_name}'")
                return None
            else:
                log.error(f"Failed to get connection groups. Status code: {r.status_code}, Response: {r.text}")
                return None
        except Exception as e:
            log.error(f"Exception finding group by name: {str(e)}")
            return None

    def delete_connection_group_by_name(self, group_name):
        """
        Delete a connection group by its name.
        
        Args:
            group_name (str): The name of the group to delete
            
        Returns:
            dict: Summary of deletion operation including success status
        """
        result = {
            'success': False,
            'message': '',
            'summary': None
        }
        
        # First, find the group
        group = self.get_connection_group_by_name(group_name)
        if not group:
            result['message'] = f"No connection group found with name '{group_name}'"
            return result
        
        # Get the group identifier and proceed with deletion
        group_identifier = group['identifier']
        deletion_summary = self.delete_connection_group_recursive(group_identifier)
        
        if not deletion_summary['errors']:
            result.update({
                'success': True,
                'message': f"Successfully deleted group '{group_name}'",
                'summary': deletion_summary
            })
        else:
            result.update({
                'success': False,
                'message': f"Errors occurred while deleting group '{group_name}'",
                'summary': deletion_summary
            })
        
        return result

# Initialize the Guac instance
guac = Guac()

# Expose the methods as module-level functions
def create_user(username):
    return guac.create_user(username)

def remove_user(username):
    return guac.remove_user(username)

def list_users():
    return guac.list_users()

def create_connection(connection_data):
    return guac.newConnection(connection_data)

def add_connection_to_user(username, connection_id):
    return guac.givePermissionToConnection(username, connection_id)

def add_user_to_connection_group(username, connection_group_id):
    return guac.add_user_to_connection_group(username, connection_group_id)

def list_connection_groups():
    return guac.list_connection_groups()

def create_connection_group(name, parent_identifier="ROOT", type="ORGANIZATIONAL"):
    return guac.create_connection_group(name, parent_identifier, type)

def delete_connection_group(group_identifier):
    return guac.delete_connection_group_recursive(group_identifier)

def delete_connection_group_by_name(group_name):
    return guac.delete_connection_group_by_name(group_name)