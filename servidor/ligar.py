# Liga um PC com Wake-on-LAN. Uso: python ligar.py AA:BB:CC:DD:EE:FF
# Rode de um aparelho sempre ligado na mesma rede (Raspberry Pi, outro PC).
import socket
import sys

mac = sys.argv[1].replace(":", "").replace("-", "")
pacote = bytes.fromhex("FF" * 6 + mac * 16)
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.sendto(pacote, ("255.255.255.255", 9))
print("Pacote enviado")
