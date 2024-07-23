import os
import requests
from dotenv import load_dotenv
from typing import List, Dict, Any
import json

load_dotenv()

NGINX_API_URL = os.getenv("NGINX_API_URL")
NGINX_USERNAME = os.getenv("NGINX_USERNAME")
NGINX_PASSWORD = os.getenv("NGINX_PASSWORD")

def get_auth_token() -> str:
    """
    Get an authentication token using username and password.
    
    Returns:
        A string containing the authentication token.
    """
    url = f"{NGINX_API_URL}/api/tokens"
    data = {
        "identity": NGINX_USERNAME,
        "secret": NGINX_PASSWORD
    }
    response = requests.post(url, json=data)
    response.raise_for_status()
    return response.json()["token"]

def list_proxy_hosts() -> List[Dict[str, Any]]:
    """
    List all proxy hosts.
    
    Returns:
        A list of dictionaries containing proxy host information.
    """
    url = f"{NGINX_API_URL}/api/nginx/proxy-hosts"
    token = get_auth_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def create_proxy_host(proxy_host_data: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{NGINX_API_URL}/api/nginx/proxy-hosts"
    token = get_auth_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    print(f"Sending request to: {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Data: {json.dumps(proxy_host_data, indent=2)}")
    response = requests.post(url, headers=headers, json=proxy_host_data)
    print(f"Response status code: {response.status_code}")
    print(f"Response content: {response.text}")
    response.raise_for_status()
    return response.json()

def list_certificates() -> List[Dict[str, Any]]:
    """
    List all SSL certificates.
    
    Returns:
        A list of dictionaries containing certificate information.
    """
    url = f"{NGINX_API_URL}/api/nginx/certificates"
    token = get_auth_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()