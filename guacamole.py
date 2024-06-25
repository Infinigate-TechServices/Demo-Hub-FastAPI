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
        self.url = os.getenv('GUACAMOLE_URL', 'http://10.40.33.208:8080/guacamole/')
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

# Initialize the GuacamoleAPI instance
guacamole_api = GuacamoleAPI()

# Expose the methods as module-level functions
def create_user(username):
    return guacamole_api.create_user(username)

def remove_user(username):
    return guacamole_api.remove_user(username)

def list_users():
    return guacamole_api.list_users()