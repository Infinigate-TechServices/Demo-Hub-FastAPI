from pywebio.input import actions
from pywebio.session import run_js
from pywebio.output import put_buttons
import pywebio_pve
import pywebio_dns
import pywebio_nginx
import pywebio_guacamole  # Import the new Guacamole management module

def pywebio_main():
    while True:
        choice = actions('Choose an option', [
            'DNS Management', 
            'PVE Management', 
            'Nginx Proxy Management',
            'Guacamole Management',  # Add the new option
            'Exit'  # Add an exit option for better user experience
        ])
        
        if choice == 'DNS Management':
            pywebio_dns.dns_management()
        
        elif choice == 'PVE Management':
            pywebio_pve.pve_management()
        
        elif choice == 'Nginx Proxy Management':
            pywebio_nginx.nginx_management()
        
        elif choice == 'Guacamole Management':
            pywebio_guacamole.guac_management()  # Call the new Guacamole management function
        
        elif choice == 'Exit':
            break  # Exit the loop and end the application
        
        put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))

if __name__ == '__main__':
    pywebio_main()