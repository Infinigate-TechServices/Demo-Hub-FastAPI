import os
import requests
from dotenv import load_dotenv

load_dotenv()

AUTHENTIK_URL = os.getenv('AUTHENTIK_URL')
AUTHENTIK_TOKEN = os.getenv('AUTHENTIK_TOKEN')

def create_user_in_authentik(username, email, name, password):
    url = f"{AUTHENTIK_URL}/api/v3/core/users/"
    headers = {
        "Authorization": f"Bearer {AUTHENTIK_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "username": username,
        "email": email,
        "name": name,
        "password": password
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 201:
        return response.json()
    else:
        raise Exception(f"Failed to create user: {response.text}")
