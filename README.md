# Training Lab Management System

A comprehensive automation system for managing training lab environments, built with FastAPI and Python. This system integrates with multiple services including Proxmox VE, Guacamole, NGINX Proxy Manager, Authentik, and FortiGate to provide a seamless training environment setup experience.

## Features

### VM Management
- Automated VM creation and configuration from templates
- Dynamic node selection based on resource availability
- Automatic VM lifecycle management (creation, startup, shutdown, deletion)
- VM scheduling with start and end date tags
- VM resource monitoring and optimization

### User Management
- Automated user creation across multiple systems:
  - Authentik (Identity Provider)
  - Apache Guacamole (Remote Access)
  - LLDAP (LDAP Server)
- Automatic group assignments and permissions
- Password generation and management

### Network Management
- DHCP reservation management via FortiGate
- DNS record management via Cloudflare
- Reverse proxy configuration via NGINX Proxy Manager
- MAC address tracking and IP assignment

### Training Management
- Bulk deployment of training environments
- Template-based configuration
- Automatic email notifications with deployment details
- Scheduling system for training start and end dates

### Web Interface
- PyWebIO-based user interface for:
  - Training seat creation
  - DNS management
  - PVE management
  - Nginx proxy management
  - Guacamole management
  - LDAP management

## Prerequisites

- Python 3.8+
- Proxmox VE environment
- Apache Guacamole server
- NGINX Proxy Manager
- Authentik installation
- FortiGate firewall
- SMTP server for notifications
- Cloudflare account (for DNS management)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd training-lab-management
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with the following variables:
```env
# Proxmox Configuration
PVE_HOST=your-proxmox-host
PVE_TOKEN_ID=your-token-id
PVE_TOKEN_SECRET=your-token-secret
PVE_PORT=8006
PVE_NODE1=node1
PVE_NODE2=node2
# Add more nodes as needed

# Authentik Configuration
AUTHENTIK_URL=your-authentik-url
AUTHENTIK_TOKEN=your-authentik-token

# Guacamole Configuration
GUACAMOLE_URL=your-guacamole-url
GUACAMOLE_USERNAME=admin
GUACAMOLE_PASSWORD=your-password

# NGINX Proxy Manager Configuration
NGINX_API_URL=your-nginx-url
NGINX_USERNAME=admin
NGINX_PASSWORD=your-password

# Cloudflare Configuration
CF_TOKEN=your-cloudflare-token
CF_ZONE_ID=your-zone-id

# FortiGate Configuration
FGT_ADDR=your-fortigate-address
FGT_API_KEY=your-api-key

# SMTP Configuration
SMTP_SERVER=your-smtp-server
SMTP_PORT=587
SMTP_USERNAME=your-username
SMTP_PASSWORD=your-password
RECIPIENT_EMAIL=recipient@example.com

# LLDAP Configuration
LLDAP_URL=your-lldap-url
LLDAP_ADMIN_USER=admin
LLDAP_ADMIN_PASSWORD=your-password
```

5. Create a `training_templates.json` file with your training configurations:
```json
[
  {
    "name": ["Training Name"],
    "template_ids": {
      "node1": 100,
      "node2": 101
    },
    "dhcp_server_id": 1,
    "connection_group_id": "1",
    "connections": [
      {
        "connection_name": "RDP - {{first_name}} {{last_name}}",
        "protocol": "rdp",
        "hostname": "localhost",
        "port": "3389",
        "username": "admin",
        "password": "password",
        "proxy_hostname": "{{guacd_proxy_ip}}",
        "proxy_port": 4822
      }
    ]
  }
]
```

## Usage

1. Start the application:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

2. Access the web interface at `http://localhost:8000`

3. To create training environments:
   - Select "Create Training Seats" from the main menu
   - Choose the training template
   - Enter ticket number and training dates
   - Input student names (one per line)
   - Submit and monitor the deployment progress

4. The system will automatically:
   - Create VMs for each student
   - Configure networking and access
   - Create user accounts
   - Set up remote access
   - Send deployment summary email

## API Documentation

The system provides a comprehensive REST API. Access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Background Tasks

The system includes several background tasks that run automatically:
- VM schedule updates (3:00 AM)
- VM start checks (3:30 AM)
- Deletion checks (4:00 AM)

## Security Considerations

- All passwords are generated securely using Python's `secrets` module
- API tokens are required for all service interactions
- SSL/TLS is enforced for all connections
- User permissions are strictly controlled
- Sensitive information is stored in environment variables

## Troubleshooting

Common issues and solutions:

1. VM Creation Failures:
   - Verify template availability
   - Check node resources
   - Ensure proper permissions

2. Network Issues:
   - Verify DHCP server configuration
   - Check FortiGate firewall rules
   - Validate DNS records

3. User Access Problems:
   - Verify user creation in all systems
   - Check group assignments
   - Validate proxy configurations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
