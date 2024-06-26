TEMPLATE_CONNECTIONS = {
    "Sophos-Firewall-Basics": [
        {"name": "admin@MUC-SFOS", "protocol": "ssh", "port": 22},
        {"name": "admin@NYC-SFOS", "protocol": "ssh", "port": 22},
        {"name": "Administrator@MUC-Client", "protocol": "rdp", "port": 3389},
        {"name": "Administrator@MUC-DC", "protocol": "rdp", "port": 3389},
        {"name": "Administrator@NYC-Client", "protocol": "rdp", "port": 3389},
        {"name": "ChrisBaum@MUC-Client", "protocol": "rdp", "port": 3389},
        {"name": "HanniBallekter@MUC-Client", "protocol": "rdp", "port": 3389},
        {"name": "IngeWahrsam@MUC-Client", "protocol": "rdp", "port": 3389},
        {"name": "localadm@NYC-Client", "protocol": "rdp", "port": 3389},
        {"name": "MarioNehse@MUC-Client", "protocol": "rdp", "port": 3389},
        {"name": "RainerZufall@MUC-Client", "protocol": "rdp", "port": 3389},
        {"name": "WandaLismus@MUC-Client", "protocol": "rdp", "port": 3389},
    ],
    "NSE4": [
        {"name": "HTTPS", "protocol": "rdp", "port": 443},
        {"name": "SSH", "protocol": "ssh", "port": 22}
    ]
}