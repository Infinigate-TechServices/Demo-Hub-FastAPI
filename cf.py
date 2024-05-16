import CloudFlare
from models import RecordA
import os
from dotenv import load_dotenv

load_dotenv()

# Get Cloudflare credentials from environment variables
cf_token = os.getenv('CF_TOKEN')
cf_zone_id = os.getenv('CF_ZONE_ID')

# Initialize the CloudFlare API with the API token
cf = CloudFlare.CloudFlare(token=cf_token)

def create_record_a(record: RecordA):
    record_data = {"type": "A", "name": record.domain, "content": record.ip, "ttl": 120}
    try:
        response = cf.zones.dns_records.post(cf_zone_id, data=record_data)
        return response
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        return {"error": str(e)}

def remove_record_a(record: RecordA):
    try:
        response = cf.zones.dns_records.delete(cf_zone_id, record.id)
        return response
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        return {"error": str(e)}

def list_seats():
    try:
        records = cf.zones.dns_records.get(cf_zone_id)
        return records
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        return {"error": str(e)}