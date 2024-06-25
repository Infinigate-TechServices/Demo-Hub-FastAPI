import os
from dotenv import load_dotenv
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import requests

load_dotenv()

LLDAP_URL = os.getenv('LLDAP_URL')
LLDAP_ADMIN_USER = os.getenv('LLDAP_ADMIN_USER')
LLDAP_ADMIN_PASSWORD = os.getenv('LLDAP_ADMIN_PASSWORD')

def get_auth_token():
    auth_url = f"{LLDAP_URL}/auth/simple/login"
    payload = {
        "username": LLDAP_ADMIN_USER,
        "password": LLDAP_ADMIN_PASSWORD
    }
    response = requests.post(auth_url, json=payload)
    if response.status_code == 200:
        return response.json()['token']
    else:
        raise Exception("Failed to get auth token")

class LLDAPAPI:
    def __init__(self):
        self.token = get_auth_token()
        transport = RequestsHTTPTransport(
            url=f"{LLDAP_URL}/api/graphql",
            headers={'Authorization': f'Bearer {self.token}'},
            use_json=True,
        )
        self.client = Client(transport=transport, fetch_schema_from_transport=True)

    def create_user(self, id, email, displayName, firstName, lastName):
        mutation = gql("""
        mutation CreateUser($user: CreateUserInput!) {
        createUser(user: $user) {
            id
            email
            displayName
            firstName
            lastName
        }
        }
        """)

        variables = {
            "user": {
                "id": id,
                "email": email,
                "displayName": displayName,
                "firstName": firstName,
                "lastName": lastName
            }
        }

        result = self.client.execute(mutation, variable_values=variables)
        return result['createUser']

    def list_users(self):
        query = gql("""
        query {
          users {
            id
            email
            displayName
            firstName
            lastName
          }
        }
        """)

        result = self.client.execute(query)
        return result['users']

    def remove_user(self, user_id):
        mutation = gql("""
        mutation DeleteUser($userId: String!) {
          deleteUser(userId: $userId) {
            ok
          }
        }
        """)

        variables = {
            "userId": user_id
        }

        result = self.client.execute(mutation, variable_values=variables)
        return result['deleteUser']['ok']
    
    def add_user_to_group(self, user_id, group_id):
        mutation = gql("""
        mutation AddUserToGroup($userId: String!, $groupId: Int!) {
        addUserToGroup(userId: $userId, groupId: $groupId) {
            ok
        }
        }
        """)

        variables = {
            "userId": user_id,
            "groupId": group_id
        }

        result = self.client.execute(mutation, variable_values=variables)
        return result['addUserToGroup']['ok']
    
    def list_groups(self):
        query = gql("""
        query {
        groups {
            id
            displayName
        }
        }
        """)

        result = self.client.execute(query)
        return result['groups']

# Initialize the LLDAPAPI instance
lldap_api = LLDAPAPI()

# Expose the methods as module-level functions
def create_user(id, email, displayName, firstName, lastName):
    return lldap_api.create_user(id, email, displayName, firstName, lastName)

def list_users():
    return lldap_api.list_users()

def remove_user(user_id):
    return lldap_api.remove_user(user_id)

def add_user_to_group(user_id, group_id):
    return lldap_api.add_user_to_group(user_id, group_id)

def list_groups():
    return lldap_api.list_groups()