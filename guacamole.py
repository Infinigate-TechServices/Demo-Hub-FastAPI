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