import logging
import urllib.parse
import requests
from dotenv import load_dotenv
import os

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class GuacamoleAPI:
    def __init__(self):
        self.url = os.getenv('GUACAMOLE_URL')
        if not self.url:
            raise ValueError("GUACAMOLE_URL environment variable is not set")
        self.token = None
        self.headers = {'Accept': 'application/json'}
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
        return self.token

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
        url = self.urljoin(self.url, f'api/session/data/{self.dataSource}/users')
        r = requests.post(url, headers=self.headers, params={'token': self.token}, json=data)
        if r.status_code == 200:
            log.info(f"User {username} created successfully")
            return True
        else:
            log.error(f"Failed to create user {username}: {r.text}")
            return False

    def remove_user(self, username):
        url = self.urljoin(self.url, f'api/session/data/{self.dataSource}/users/{self.urlescape(username)}')
        r = requests.delete(url, headers=self.headers, params={'token': self.token})
        if r.status_code == 204:
            log.info(f"User {username} removed successfully")
            return True
        else:
            log.error(f"Failed to remove user {username}: {r.text}")
            return False

    def list_users(self):
        url = self.urljoin(self.url, f'api/session/data/{self.dataSource}/users')
        r = requests.get(url, headers=self.headers, params={'token': self.token})
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

    def create_rdp_connection(self, connection_name, hostname, port=3389, username="", password="", domain="",
                            security="nla", ignore_cert=True, enable_font_smoothing=True,
                            server_layout="de-de-qwertz", guacd_hostname="", guacd_port=""):
        connection = RDP_CONNECTION.copy()
        connection["name"] = connection_name
        connection["parameters"].update({
            "hostname": hostname,
            "port": str(port),  # Ensure this value is a string
            "username": username,
            "password": password,
            "domain": domain,
            "security": security,
            "ignore-cert": "true" if ignore_cert else "false",
            "enable-font-smoothing": "true" if enable_font_smoothing else "false",
            "server-layout": server_layout
        })
        if guacd_hostname:
            connection["attributes"]["guacd-hostname"] = guacd_hostname
        if guacd_port:
            connection["attributes"]["guacd-port"] = str(guacd_port)  # Ensure this value is a string

        url = self.urljoin(self.url, f'api/session/data/{self.dataSource}/connections')
        r = requests.post(url, headers=self.headers, params={'token': self.token}, json=connection)
        if r.status_code == 200:
            log.info(f"RDP connection '{connection_name}' created successfully")
            return r.json()
        else:
            log.error(f"Failed to create RDP connection '{connection_name}': {r.text}")
            return None
        
    def create_connection(self, connection_data):
        connection = {
            "name": connection_data.get("connection_name"),
            "parent_id": connection_data.get("parent_id"),
            "protocol": connection_data.get("protocol"),
            "parameters": {},
            "attributes": {
                "guacd-hostname": connection_data.get("proxy_hostname"),
                "guacd-port": str(connection_data.get("proxy_port"))
            }
        }

        # Add common parameters
        common_params = ["hostname", "port", "username", "password"]
        for param in common_params:
            if param in connection_data:
                connection["parameters"][param] = str(connection_data[param])

        # Add protocol-specific parameters
        if connection_data["protocol"] == "rdp":
            rdp_params = ["domain", "ignore-cert", "security", "server-layout", "enable-font-smoothing"]
            for param in rdp_params:
                if param in connection_data:
                    connection["parameters"][param] = str(connection_data[param]).lower()

        elif connection_data["protocol"] == "ssh":
            ssh_params = ["color-scheme", "font-name", "font-size"]
            for param in ssh_params:
                if param in connection_data:
                    connection["parameters"][param] = str(connection_data[param])

        # You can add more protocol-specific parameters here for other protocols

        url = self.urljoin(self.url, f'api/session/data/{self.dataSource}/connections')
        r = requests.post(url, headers=self.headers, params={'token': self.token}, json=connection)
        
        if r.status_code == 200:
            log.info(f"Connection '{connection['name']}' created successfully")
            return r.json()
        else:
            log.error(f"Failed to create connection '{connection['name']}': {r.text}")
            return None
    def add_connection_to_user(self, username, connection_id):
        url = self.urljoin(self.url, f'api/session/data/{self.dataSource}/users/{self.urlescape(username)}/permissions')
        
        payload = [
            {
                "op": "add",
                "path": f"/connectionPermissions/{connection_id}",
                "value": "READ"
            }
        ]

        try:
            r = requests.patch(url, headers=self.headers, params={'token': self.token}, json=payload)
            r.raise_for_status()
            log.info(f"Connection {connection_id} added to user {username} successfully")
            return True
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to add connection {connection_id} to user {username}: {str(e)}")
            if e.response is not None:
                log.error(f"Response content: {e.response.text}")
            return False, str(e)

    def get_connection_id(self, connection_name):
        url = self.urljoin(self.url, f'api/session/data/{self.dataSource}/connections')
        
        try:
            r = requests.get(url, headers=self.headers, params={'token': self.token})
            r.raise_for_status()
            connections = r.json()
            
            for conn_id, conn_data in connections.items():
                if conn_data['name'] == connection_name:
                    log.info(f"Found connection '{connection_name}' with ID: {conn_id}")
                    return conn_id
            
            log.warning(f"No connection found with name: {connection_name}")
            return None
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to retrieve connections: {str(e)}")
            if e.response is not None:
                log.error(f"Response content: {e.response.text}")
            return None

# Expose the method as a module-level function
def add_connection_to_user(username, connection_id):
    return guacamole_api.add_connection_to_user(username, connection_id)

# Initialize the GuacamoleAPI instance
guacamole_api = GuacamoleAPI()

# Expose the methods as module-level functions
def create_user(username):
    return guacamole_api.create_user(username)

def remove_user(username):
    return guacamole_api.remove_user(username)

def list_users():
    return guacamole_api.list_users()

def create_rdp_connection(connection_name, hostname, **kwargs):
    return guacamole_api.create_rdp_connection(connection_name, hostname, **kwargs)

def add_connection_to_user(username, connection_id):
    return guacamole_api.add_connection_to_user(username, connection_id)

def get_connection_id(connection_name):
    return guacamole_api.get_connection_id(connection_name)

def create_connection(connection_data):
    return guacamole_api.create_connection(connection_data)