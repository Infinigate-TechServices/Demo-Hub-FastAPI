import os
import requests
from dotenv import load_dotenv
from models import ProxyHost
import threading

load_dotenv()

NGINX_API_URL = os.getenv("NGINX_API_URL")
NGINX_USERNAME = os.getenv("NGINX_USERNAME")
NGINX_PASSWORD = os.getenv("NGINX_PASSWORD")

token_lock = threading.Lock()
NGINX_API_TOKEN = None

headers = {
    "Content-Type": "application/json"
}

def fetch_token():
    global NGINX_API_TOKEN
    url = f"{NGINX_API_URL}/tokens"
    response = requests.post(url, json={
        "identity": NGINX_USERNAME,
        "secret": NGINX_PASSWORD,
        "scope": "user"
    })
    data = response.json()
    with token_lock:
        NGINX_API_TOKEN = data['token']
        headers["Authorization"] = f"Bearer {NGINX_API_TOKEN}"

def token_refresher():
    while True:
        fetch_token()
        # Refresh token every hour (assuming token is valid for an hour)
        time.sleep(3600)

# Start the token refresher thread
token_thread = threading.Thread(target=token_refresher)
token_thread.daemon = True
token_thread.start()

def create_proxy_host(proxy_host: ProxyHost):
    url = f"{NGINX_API_URL}/nginx/proxy-hosts"
    response = requests.post(url, headers=headers, json=proxy_host.dict())
    return response.json()

def remove_proxy_host(proxy_host_id: int):
    url = f"{NGINX_API_URL}/nginx/proxy-hosts/{proxy_host_id}"
    response = requests.delete(url, headers=headers)
    return response.json()

def list_proxy_hosts():
    url = f"{NGINX_API_URL}/nginx/proxy-hosts"
    response = requests.get(url, headers=headers)
    return response.json()
