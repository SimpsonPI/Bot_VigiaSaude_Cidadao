import socket
orig = socket.getaddrinfo
def my_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return orig(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = my_getaddrinfo

import httpx
try:
    print("Status:", httpx.get('https://api.telegram.org').status_code)
except Exception as e:
    print("Erro:", e)
    