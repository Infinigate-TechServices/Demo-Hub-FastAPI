from pywebio.input import actions, input
from pywebio.output import put_text, put_buttons, put_error, put_success, put_table
from pywebio.session import run_js
import requests
from datetime import datetime

API_BASE_URL = "http://localhost:8081/api"

def format_timestamp(timestamp):
    if timestamp is None or timestamp == 'N/A':
        return 'Never'
    try:
        # Convert milliseconds to seconds
        timestamp_seconds = int(timestamp) / 1000
        dt = datetime.fromtimestamp(timestamp_seconds)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return 'Invalid Date'

def guac_management():
    while True:
        guac_choice = actions('Choose Guacamole action', [
            'Create User', 'Delete User', 'List Users', 'Return to Main Menu'
        ])
        if guac_choice == 'Create User':
            username = input("Enter username for new Guacamole user:", required=True)
            try:
                response = requests.post(f"{API_BASE_URL}/v1/guacamole/users/{username}")
                response.raise_for_status()
                put_success(f"User '{username}' created successfully in Guacamole.")
            except requests.RequestException as e:
                put_error(f"Failed to create user '{username}' in Guacamole. Error: {str(e)}")
        
        elif guac_choice == 'Delete User':
            username = input("Enter username of Guacamole user to delete:", required=True)
            try:
                response = requests.delete(f"{API_BASE_URL}/v1/guacamole/users/{username}")
                response.raise_for_status()
                put_success(f"User '{username}' deleted successfully from Guacamole.")
            except requests.RequestException as e:
                put_error(f"Failed to delete user '{username}' from Guacamole. Error: {str(e)}")
        
        elif guac_choice == 'List Users':
            try:
                response = requests.get(f"{API_BASE_URL}/v1/guacamole/users")
                response.raise_for_status()
                users = response.json()
                
                if not users:
                    put_text("No users found in Guacamole.")
                else:
                    table = [['Username', 'Last Active']]
                    for username, user_info in users.items():
                        last_active = format_timestamp(user_info.get('lastActive'))
                        table.append([username, last_active])
                    
                    put_text("Guacamole Users:")
                    put_table(table)
            except requests.RequestException as e:
                put_error(f"Failed to retrieve users from Guacamole. Error: {str(e)}")
                
        elif guac_choice == 'Return to Main Menu':
            break
    
    put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))

if __name__ == "__main__":
    guac_management()