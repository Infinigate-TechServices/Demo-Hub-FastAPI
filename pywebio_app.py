from pywebio.input import actions
from pywebio.session import run_js
from pywebio.output import put_buttons
import pywebio_pve
import pywebio_dns
import pywebio_nginx

def pywebio_main():
    while True:
        choice = actions('Choose an option', ['DNS Management', 'PVE Management', 'Nginx Proxy Management'])
        
        if choice == 'DNS Management':
            pywebio_dns.dns_management()
        
        elif choice == 'PVE Management':
            pywebio_pve.pve_management()
        
        elif choice == 'Nginx Proxy Management':
            pywebio_nginx.nginx_management()
        
        put_buttons(['Return to Main Menu'], onclick=lambda _: run_js('location.reload()'))

if __name__ == '__main__':
    pywebio_main()
