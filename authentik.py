import os
import requests
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

AUTHENTIK_URL = os.getenv('AUTHENTIK_URL')
AUTHENTIK_TOKEN = os.getenv('AUTHENTIK_TOKEN')

def get_headers():
    return {
        "Authorization": f"Bearer {AUTHENTIK_TOKEN}",
        "Content-Type": "application/json"
    }

def create_user_in_authentik(username: str, email: str, name: str, password: str):
    url = f"{AUTHENTIK_URL}/api/v3/core/users/"
    payload = {
        "username": username,
        "email": email,
        "name": name
    }

    response = requests.post(url, json=payload, headers=get_headers())

    if response.status_code == 201:
        user_data = response.json()
        user_id = user_data['pk']
        set_user_password(user_id, password)
        return user_data
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to create user: {response.text}")

def set_user_password(user_id: int, password: str):
    url = f"{AUTHENTIK_URL}/api/v3/core/users/{user_id}/set_password/"
    payload = {
        "password": password
    }

    response = requests.post(url, json=payload, headers=get_headers())

    if response.status_code == 204:
        return {"message": f"Password set successfully for user {user_id}"}
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to set password: {response.text}")

def add_user_to_group(user_id: int, group_id: int):
    url = f"{AUTHENTIK_URL}/api/v3/core/groups/{group_id}/users/"
    payload = {
        "pk": user_id
    }

    response = requests.post(url, json=payload, headers=get_headers())

    if response.status_code == 204:
        return {"message": f"User {user_id} added to group {group_id} successfully"}
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to add user to group: {response.text}")

def get_user_id(username: str):
    url = f"{AUTHENTIK_URL}/api/v3/core/users/"
    params = {"username": username}
    response = requests.get(url, headers=get_headers(), params=params)

    if response.status_code == 200:
        users = response.json()
        if users['pagination']['count'] > 0:
            return users['results'][0]['pk']
        else:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to get user: {response.text}")

def get_group_id(group_name: str):
    url = f"{AUTHENTIK_URL}/api/v3/core/groups/"
    params = {"name": group_name}
    response = requests.get(url, headers=get_headers(), params=params)

    if response.status_code == 200:
        groups = response.json()
        if groups['pagination']['count'] > 0:
            return groups['results'][0]['pk']
        else:
            raise HTTPException(status_code=404, detail=f"Group '{group_name}' not found")
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to get group: {response.text}")

def list_users():
    url = f"{AUTHENTIK_URL}/api/v3/core/users/"
    response = requests.get(url, headers=get_headers())

    if response.status_code == 200:
        return response.json()['results']
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to list users: {response.text}")

def list_groups():
    url = f"{AUTHENTIK_URL}/api/v3/core/groups/"
    response = requests.get(url, headers=get_headers())

    if response.status_code == 200:
        return response.json()['results']
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to list groups: {response.text}")
    
def user_exists(username: str) -> bool:
    url = f"{AUTHENTIK_URL}/api/v3/core/users/"
    params = {"username": username}
    response = requests.get(url, headers=get_headers(), params=params)

    if response.status_code == 200:
        users = response.json()
        return users['pagination']['count'] > 0
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to check user existence: {response.text}")

def create_user_if_not_exists(username: str, email: str, name: str, password: str):
    if user_exists(username):
        return {"message": f"User '{username}' already exists"}
    else:
        return create_user_in_authentik(username, email, name, password)