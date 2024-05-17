from pywebio.input import actions, input, input_group, TEXT
from pywebio.output import put_text, put_table, put_error, put_buttons
from pywebio.session import run_js
import requests

API_BASE_URL = "http://localhost:8081/api"

def dns_management():
    dns_choice = actions('Choose DNS action', [
        'Create Record', 'Remove Record', 'List Records', 'List Training Records', 'Return to Main Menu'
    ])
    
    if dns_choice == 'Create Record':
        domain = input("Enter domain")
        ip = input("Enter IP")
        response = requests.post(f"{API_BASE_URL}/v1/dns/create-record-a", json={"domain": domain, "ip": ip})
        if response.status_code == 200:
            put_text("Record created successfully!")
        else:
            put_error("Failed to create record.")
    elif dns_choice == 'Remove Record':
        record_id = input("Enter Record ID")
        response = requests.post(f"{API_BASE_URL}/v1/dns/remove-record-a", json={"id": record_id})
        if response.status_code == 200:
            put_text("Record removed successfully!")
        else:
            put_error("Failed to remove record.")
    elif dns_choice == 'List Records':
        response = requests.get(f"{API_BASE_URL}/v1/dns/list-seats")
        if response.status_code == 200:
            records = response.json()
            table_data = [["ID", "Name", "Content", "TTL", "Comment"]]
            for record in records:
                table_data.append([
                    record.get('id'),
                    record.get('name'),
                    record.get('content'),
                    record.get('ttl'),
                    record.get('comment')
                ])
            put_table(table_data)
        else:
            put_error("Failed to retrieve DNS records.")
    elif dns_choice == 'List Training Records':
        response = requests.get(f"{API_BASE_URL}/v1/dns/list-seats")
        if response.status_code == 200:
            records = response.json()
            training_records = [record for record in records if record.get('name').endswith('student.infinigate-labs.com')]
            table_data = [["ID", "Name", "Content", "TTL", "Comment"]]
            for record in training_records:
                table_data.append([
                    record.get('id'),
                    record.get('name'),
                    record.get('content'),
                    record.get('ttl'),
                    record.get('comment')
                ])
            put_table(table_data)
        else:
            put_error("Failed to retrieve DNS records.")
    
    put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))

if __name__ == '__main__':
    dns_management()
