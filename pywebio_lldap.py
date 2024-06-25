from pywebio.input import input, select, actions
from pywebio.output import put_text, put_table, put_buttons, put_error, put_success
from pywebio.session import run_js
import requests

API_BASE_URL = "http://localhost:8081/api"

def lldap_management():
    while True:
        choice = actions('Choose LLDAP action', [
            'Create User', 'List Users', 'Delete User', 'Return to Main Menu'
        ])

        if choice == 'Create User':
            create_lldap_user()
        elif choice == 'List Users':
            list_lldap_users()
        elif choice == 'Delete User':
            delete_lldap_user()
        elif choice == 'Return to Main Menu':
            break

    put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))

def create_lldap_user():
    first_name = input("First Name", required=True)
    last_name = input("Last Name", required=True)
    
    # Fetch available groups
    groups = fetch_groups()
    group_choices = {group['displayName']: str(group['id']) for group in groups}
    
    selected_group_name = select("Select a group", options=list(group_choices.keys()))
    selected_group_id = group_choices[selected_group_name]

    user_data = {
        "id": f"{first_name.lower()}.{last_name.lower()}",
        "email": f"{first_name.lower()}.{last_name.lower()}@infinigate-labs.com",
        "displayName": f"{first_name} {last_name}",
        "firstName": first_name,
        "lastName": last_name,
        "groupId": int(selected_group_id)
    }

    try:
        response = requests.post(f"{API_BASE_URL}/v1/lldap/users", json=user_data)
        response.raise_for_status()
        result = response.json()
        put_success(f"User {result['user']['displayName']} created successfully")
        put_text(f"User ID: {result['user']['id']}")
        put_text(f"Email: {result['user']['email']}")
        put_text(f"Added to group: {selected_group_name}")
    except requests.RequestException as e:
        put_error(f"Failed to create user: {str(e)}")
        if e.response is not None:
            put_error(f"Response: {e.response.text}")

def fetch_groups():
    try:
        response = requests.get(f"{API_BASE_URL}/v1/lldap/groups")
        response.raise_for_status()
        return response.json()['groups']
    except requests.RequestException as e:
        put_error(f"Failed to fetch groups: {str(e)}")
        return []

def list_lldap_users():
    try:
        response = requests.get(f"{API_BASE_URL}/v1/lldap/users")
        response.raise_for_status()
        users = response.json()['users']

        if not users:
            put_text("No users found")
        else:
            table = [['ID', 'Email', 'Display Name', 'First Name', 'Last Name']]
            for user in users:
                table.append([
                    user.get('id', 'N/A'),
                    user.get('email', 'N/A'),
                    user.get('displayName', 'N/A'),
                    user.get('firstName', 'N/A'),
                    user.get('lastName', 'N/A')
                ])
            put_table(table)
    except requests.RequestException as e:
        put_error(f"Failed to retrieve users: {str(e)}")

def delete_lldap_user():
    user_id = input("Enter the ID of the user to delete", required=True)

    try:
        response = requests.delete(f"{API_BASE_URL}/v1/lldap/users/{user_id}")
        response.raise_for_status()
        put_success(f"User {user_id} deleted successfully")
    except requests.RequestException as e:
        put_error(f"Failed to delete user: {str(e)}")

if __name__ == "__main__":
    lldap_management()