from pywebio.input import actions, input, input_group, NUMBER, TEXT
from pywebio.output import put_text, put_table, put_error, put_buttons
from pywebio.session import run_js
import requests

API_BASE_URL = "http://localhost:8081/api"

def nginx_management():
    nginx_choice = actions('Choose Nginx Proxy action', [
        'Create Proxy Host', 'Remove Proxy Host', 'List Proxy Hosts', 'Return to Main Menu'
    ])
    
    if nginx_choice == 'Create Proxy Host':
        data = input_group("Create Proxy Host", [
            input("Domain Names (comma separated)", name="domain_names", type=TEXT),
            input("Forward Host", name="forward_host", type=TEXT),
            input("Forward Port", name="forward_port", type=NUMBER),
            input("Access List ID", name="access_list_id", type=NUMBER, value=0),
            input("Certificate ID", name="certificate_id", type=NUMBER, value=0),
            input("SSL Forced", name="ssl_forced", type=NUMBER, value=0),
            input("Caching Enabled", name="caching_enabled", type=NUMBER, value=0),
            input("Block Exploits", name="block_exploits", type=NUMBER, value=0),
            input("Advanced Config", name="advanced_config", type=TEXT, value=""),
            input("Allow Websocket Upgrade", name="allow_websocket_upgrade", type=NUMBER, value=0),
            input("HTTP2 Support", name="http2_support", type=NUMBER, value=0),
            input("Forward Scheme", name="forward_scheme", type=TEXT, value="http"),
            input("Enabled", name="enabled", type=NUMBER, value=1),
            input("HSTS Enabled", name="hsts_enabled", type=NUMBER, value=0),
            input("HSTS Subdomains", name="hsts_subdomains", type=NUMBER, value=0),
            input("Use Default Location", name="use_default_location", type=NUMBER, value=1),
            input("IPv6", name="ipv6", type=NUMBER, value=1)
        ])
        domain_names = [domain.strip() for domain in data['domain_names'].split(',')]
        proxy_host = {
            "domain_names": domain_names,
            "forward_host": data['forward_host'],
            "forward_port": data['forward_port'],
            "access_list_id": data['access_list_id'] if data['access_list_id'] != 0 else None,
            "certificate_id": data['certificate_id'] if data['certificate_id'] != 0 else None,
            "ssl_forced": bool(data['ssl_forced']),
            "caching_enabled": bool(data['caching_enabled']),
            "block_exploits": bool(data['block_exploits']),
            "advanced_config": data['advanced_config'],
            "allow_websocket_upgrade": bool(data['allow_websocket_upgrade']),
            "http2_support": bool(data['http2_support']),
            "forward_scheme": data['forward_scheme'],
            "enabled": bool(data['enabled']),
            "hsts_enabled": bool(data['hsts_enabled']),
            "hsts_subdomains": bool(data['hsts_subdomains']),
            "meta": {},
            "locations": []
        }
        response = requests.post(f"{API_BASE_URL}/v1/nginx/create-proxy-host", json=proxy_host)
        if response.status_code == 200:
            put_text("Proxy host created successfully!")
            put_text(response.json())
        else:
            put_error("Failed to create proxy host.")
        put_buttons(['Return to Nginx Management'], onclick=lambda _: run_js('location.reload()'))
    elif nginx_choice == 'Remove Proxy Host':
        proxy_host_id = input("Enter Proxy Host ID to Remove", type=NUMBER)
        response = requests.delete(f"{API_BASE_URL}/v1/nginx/remove-proxy-host/{proxy_host_id}")
        if response.status_code == 200:
            put_text("Proxy host removed successfully!")
            put_text(response.json())
        else:
            put_error("Failed to remove proxy host.")
        put_buttons(['Return to Nginx Management'], onclick=lambda _: run_js('location.reload()'))
    elif nginx_choice == 'List Proxy Hosts':
        response = requests.get(f"{API_BASE_URL}/v1/nginx/list-proxy-hosts")
        if response.status_code == 200:
            hosts = response.json()
            table_data = [["ID", "Domain Names", "Forward Host", "Forward Port"]]
            for host in hosts:
                table_data.append([host['id'], ', '.join(host['domain_names']), host['forward_host'], host['forward_port']])
            put_table(table_data)
        else:
            put_error("Failed to retrieve proxy hosts.")
        put_buttons(['Return to Nginx Management'], onclick=lambda _: run_js('location.reload()'))
    elif nginx_choice == 'Return to Main Menu':
        run_js('location.reload()')

if __name__ == '__main__':
    nginx_management()
