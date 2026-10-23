import hmac
import io
import json
import ipaddress
import os
import secrets
import socket
import subprocess
import time
from pathlib import Path

from ctypes import POINTER, cast

import comtypes
import psutil
import pyperclip
from comtypes import CLSCTX_ALL
from flask import Flask, Response, abort, jsonify, request, send_from_directory
from PIL import ImageGrab
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from pynput.keyboard import Controller, Key
from pynput.mouse import Button, Controller as Mouse

PORTA = 5000
REDE_TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
BASE = Path(__file__).parent
ARQUIVO_TOKEN = BASE / "token.txt"

app = Flask(__name__)
teclado = Controller()
falhas = {}  # ip -> (tentativas erradas, bloqueado até)

ACOES = {
    "desligar": (["shutdown", "/s", "/t", "10"], "Desligando em 10 segundos"),
    "reiniciar": (["shutdown", "/r", "/t", "10"], "Reiniciando em 10 segundos"),
    "cancelar": (["shutdown", "/a"], "Desligamento cancelado"),
    "bloquear": (["rundll32.exe", "user32.dll,LockWorkStation"], "PC bloqueado"),
    "suspender": (["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], "Suspendendo o PC"),
}

TECLAS = {
    "volume_mais": Key.media_volume_up,
    "volume_menos": Key.media_volume_down,
    "mudo": Key.media_volume_mute,
    "play_pause": Key.media_play_pause,
    "proxima": Key.media_next,
    "anterior": Key.media_previous,
    "enter": Key.enter,
    "esc": Key.esc,
    "apagar": Key.backspace,
    "tab": Key.tab,
    "espaco": Key.space,
    "esquerda": Key.left,
    "direita": Key.right,
    "cima": Key.up,
    "baixo": Key.down,
}


def carregar_token():
    token = os.environ.get("PC_TOKEN")
    if token:
        return token
    if ARQUIVO_TOKEN.exists():
        return ARQUIVO_TOKEN.read_text().strip()
    token = secrets.token_urlsafe(8)
    ARQUIVO_TOKEN.write_text(token)
    return token


TOKEN = carregar_token()


def ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "IP-DO-PC"
    finally:
        s.close()


@app.before_request
def proteger():
    # Só aceita conexões da rede local
    ip = ipaddress.ip_address(request.remote_addr)
    if not (ip.is_private or ip.is_loopback or ip in REDE_TAILSCALE):
        abort(403)
    if not request.path.startswith("/api/"):
        return

    agora = time.time()
    erros, ate = falhas.get(request.remote_addr, (0, 0))
    if erros >= 5 and agora < ate:
        return jsonify(msg="Muitas tentativas. Aguarde 1 minuto."), 429

    enviado = request.headers.get("X-Token", "").encode()
    if not hmac.compare_digest(enviado, TOKEN.encode()):
        falhas[request.remote_addr] = (erros + 1, agora + 60)
        return jsonify(msg="Token incorreto"), 401
    falhas.pop(request.remote_addr, None)


@app.get("/")
def home():
    return send_from_directory(BASE, "index.html")


@app.post("/api/ping")
def ping():
    return jsonify(msg="Conectado")


@app.post("/api/tecla")
def tecla():
    nome = (request.get_json(silent=True) or {}).get("tecla")
    tecla_pynput = TECLAS.get(nome)
    if tecla_pynput is None:
        return jsonify(msg="Tecla desconhecida"), 400
    teclado.tap(tecla_pynput)
    return jsonify(msg="Enviado")


@app.post("/api/texto")
def texto():
    conteudo = str((request.get_json(silent=True) or {}).get("texto", ""))[:500]
    if not conteudo:
        return jsonify(msg="Digite algum texto"), 400
    teclado.type(conteudo)
    return jsonify(msg="Texto digitado")


@app.post("/api/<acao>")
def energia(acao):
    item = ACOES.get(acao)
    if item is None:
        return jsonify(msg="Ação desconhecida"), 404
    comando, mensagem = item
    subprocess.Popen(comando)
    return jsonify(msg=mensagem)


mouse_ctl = Mouse()


@app.post("/api/mouse")
def mouse_rota():
    d = request.get_json(silent=True) or {}
    if "mover" in d:
        dx, dy = d["mover"]
        mouse_ctl.move(int(dx), int(dy))
    elif "rolar" in d:
        mouse_ctl.scroll(0, int(d["rolar"]))
    elif d.get("clique") == "duplo":
        mouse_ctl.click(Button.left, 2)
    elif d.get("clique") in ("esquerdo", "direito"):
        mouse_ctl.click(Button.left if d["clique"] == "esquerdo" else Button.right)
    return jsonify(msg="ok")


@app.post("/api/volume")
def volume_rota():
    nivel = (request.get_json(silent=True) or {}).get("nivel")
    comtypes.CoInitialize()
    try:
        dispositivo = AudioUtilities.GetSpeakers()
        iface = dispositivo.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        v = cast(iface, POINTER(IAudioEndpointVolume))
        if nivel is not None:
            v.SetMasterVolumeLevelScalar(max(0, min(100, int(nivel))) / 100, None)
        atual = round(v.GetMasterVolumeLevelScalar() * 100)
    finally:
        comtypes.CoUninitialize()
    return jsonify(msg=f"Volume {atual}%", nivel=atual)


@app.post("/api/status")
def status():
    return jsonify(
        cpu=psutil.cpu_percent(interval=0.3),
        ram=psutil.virtual_memory().percent,
        disco=psutil.disk_usage(BASE.anchor).percent,
    )


@app.post("/api/desligar_em")
def desligar_em():
    minutos = int((request.get_json(silent=True) or {}).get("min", 0))
    if not 1 <= minutos <= 600:
        return jsonify(msg="Escolha entre 1 e 600 minutos"), 400
    subprocess.Popen(["shutdown", "/s", "/t", str(minutos * 60)])
    return jsonify(msg=f"Desligando em {minutos} min")


def ler_atalhos():
    try:
        return json.loads((BASE / "atalhos.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


@app.post("/api/atalhos")
def lista_atalhos():
    return jsonify(itens=[a["nome"] for a in ler_atalhos()])


APPS = {}


def abrir_app_uwp(nome):
    """Plano B: apps da Microsoft Store, achados pelo Get-StartApps."""
    chave = nome.lower()
    if chave not in APPS:
        cmd = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"
        saida = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).stdout
        try:
            apps = json.loads(saida)
        except ValueError:
            return False
        if isinstance(apps, dict):
            apps = [apps]
        achados = [a for a in apps if chave in a["Name"].lower()]
        if not achados:
            return False
        achados.sort(key=lambda a: (a["Name"].lower() != chave, len(a["Name"])))
        APPS[chave] = achados[0]["AppID"]
    subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + APPS[chave]])
    return True


PASTAS_MENU = [
    Path(os.environ[v]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    for v in ("ProgramData", "APPDATA")
    if v in os.environ
]


def achar_atalho(nome):
    """Procura o atalho do programa no Menu Iniciar (inclui apps do Chrome/Edge)."""
    chave = nome.lower()
    achados = []
    for pasta in PASTAS_MENU:
        for lnk in pasta.rglob("*.lnk"):
            n = lnk.stem.lower()
            if chave in n and "uninstall" not in n and "desinstal" not in n:
                achados.append(lnk)
    achados.sort(key=lambda l: (l.stem.lower() != chave, len(l.stem)))
    return achados[0] if achados else None


def abrir_app(nome):
    """Abre um programa pelo nome, como aparece no Menu Iniciar."""
    lnk = achar_atalho(nome)
    if lnk:
        try:
            os.startfile(str(lnk))
            return True
        except OSError:
            pass
    return abrir_app_uwp(nome)


@app.post("/api/abrir")
def abrir():
    i = (request.get_json(silent=True) or {}).get("i")
    lista = ler_atalhos()
    if not isinstance(i, int) or not 0 <= i < len(lista):
        return jsonify(msg="Atalho inválido"), 400
    alvo = lista[i]["alvo"]
    if alvo.startswith("app:"):
        if not abrir_app(alvo[4:].strip()):
            return jsonify(msg=f"App não encontrado: {alvo[4:]}"), 404
    else:
        os.startfile(alvo)
    return jsonify(msg=f"Abrindo {lista[i]['nome']}")


@app.post("/api/area")
def area():
    d = request.get_json(silent=True) or {}
    conteudo = str(d.get("texto", ""))[:5000]
    if not conteudo:
        return jsonify(msg="Escreva algo primeiro"), 400
    pyperclip.copy(conteudo)
    if d.get("colar"):
        with teclado.pressed(Key.ctrl):
            teclado.tap("v")
        return jsonify(msg="Colado no PC")
    return jsonify(msg="Copiado no PC")


@app.post("/api/tela")
def tela():
    img = ImageGrab.grab()
    img.thumbnail((1280, 720))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=55)
    return Response(buf.getvalue(), mimetype="image/jpeg")


@app.get("/manifest.json")
@app.get("/icone.png")
def estaticos():
    return send_from_directory(BASE, request.path.lstrip("/"))


if __name__ == "__main__":
    print(f"\nAbra no celular: http://{ip_local()}:{PORTA}")
    print(f"Token: {TOKEN}\n")
    app.run(host="0.0.0.0", port=PORTA)
