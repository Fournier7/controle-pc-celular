import asyncio
import base64
import hmac
import io
import json
import ipaddress
import os
import secrets
import socket
import subprocess
import threading
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
from pynput.keyboard import Controller, Key, KeyCode
from pynput.mouse import Button, Controller as Mouse

def vk(letra):
    """Letra enviada como tecla de verdade (código virtual), e não como texto.
    Atalhos de outros programas só reconhecem assim."""
    return KeyCode.from_vk(ord(letra.upper()))


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
CATALOGO_APPS = None
TRAVA_APPS = threading.Lock()
REPETIR_BUSCA_APPS_EM = 0


def carregar_apps_uwp():
    """Consulta a lista uma vez por execução; não abre nenhum programa."""
    global CATALOGO_APPS, REPETIR_BUSCA_APPS_EM
    with TRAVA_APPS:
        if CATALOGO_APPS is not None:
            return CATALOGO_APPS
        if time.monotonic() < REPETIR_BUSCA_APPS_EM:
            return []
        cmd = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"
        try:
            resultado = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True, text=True, encoding="utf-8", timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if resultado.returncode != 0:
                raise ValueError("Não foi possível consultar os aplicativos")
            dados = json.loads(resultado.stdout)
            if isinstance(dados, dict):
                dados = [dados]
            if dados is None:
                dados = []
            if not isinstance(dados, list):
                raise ValueError("Lista de aplicativos inválida")
            CATALOGO_APPS = [a for a in dados if isinstance(a, dict)
                             and isinstance(a.get("Name"), str)
                             and isinstance(a.get("AppID"), str)]
        except (OSError, ValueError, subprocess.TimeoutExpired):
            # Evita disparar consultas lentas em sequência quando o PowerShell falha.
            REPETIR_BUSCA_APPS_EM = time.monotonic() + 30
            return []
        return CATALOGO_APPS


def abrir_app_uwp(nome):
    """Plano B: busca no catálogo preparado ao iniciar o servidor."""
    chave = nome.lower()
    if chave not in APPS:
        achados = [a for a in carregar_apps_uwp() if chave in a["Name"].lower()]
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
            teclado.tap(vk("v"))
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


def volume_do_microfone():
    """Controle de volume/mudo do microfone padrão do Windows."""
    try:
        dispositivo = AudioUtilities.GetMicrophone()
    except AttributeError:
        from pycaw.pycaw import IMMDeviceEnumerator
        enumerador = comtypes.CoCreateInstance(
            comtypes.GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}"),
            IMMDeviceEnumerator, comtypes.CLSCTX_INPROC_SERVER)
        dispositivo = enumerador.GetDefaultAudioEndpoint(1, 1)  # 1 = captura
    iface = dispositivo.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(iface, POINTER(IAudioEndpointVolume))


@app.post("/api/microfone")
def microfone():
    acao = (request.get_json(silent=True) or {}).get("acao", "estado")
    comtypes.CoInitialize()
    try:
        v = volume_do_microfone()
        if acao == "alternar":
            v.SetMute(0 if v.GetMute() else 1, None)
        mudo = bool(v.GetMute())
    except Exception:
        return jsonify(msg="Não achei o microfone padrão do Windows"), 500
    finally:
        comtypes.CoUninitialize()
    return jsonify(msg="Microfone mutado" if mudo else "Microfone ligado", mudo=mudo)


# Atalhos globais que você cria no Discord (Configurações > Atalhos)
DISCORD_TECLAS = {"mutar": vk("m"), "ensurdecer": vk("d")}


@app.post("/api/discord")
def discord():
    tecla = DISCORD_TECLAS.get((request.get_json(silent=True) or {}).get("acao"))
    if tecla is None:
        return jsonify(msg="Ação desconhecida"), 400
    with teclado.pressed(Key.ctrl, Key.shift, Key.alt):
        teclado.tap(tecla)
    return jsonify(msg="Atalho do Discord enviado")


COMBOS = {
    "alt_tab": ([Key.alt], Key.tab),
    "area_trabalho": ([Key.cmd], vk("d")),
    "fechar_janela": ([Key.alt], Key.f4),
    "captura": ([Key.cmd, Key.shift], vk("s")),
    "tela_cheia": ([], Key.f11),
    "gerenciador": ([Key.ctrl, Key.shift], Key.esc),
    "copiar": ([Key.ctrl], vk("c")),
    "colar": ([Key.ctrl], vk("v")),
    "desfazer": ([Key.ctrl], vk("z")),
}


@app.post("/api/combo")
def combo():
    item = COMBOS.get((request.get_json(silent=True) or {}).get("nome"))
    if item is None:
        return jsonify(msg="Atalho desconhecido"), 400
    modificadores, tecla = item
    with teclado.pressed(*modificadores):
        teclado.tap(tecla)
    return jsonify(msg="Enviado")


def nome_da_sessao(s):
    try:
        return s.Process.name() if s.Process else None
    except Exception:
        return None


@app.post("/api/apps_audio")
def apps_audio():
    d = request.get_json(silent=True) or {}
    comtypes.CoInitialize()
    try:
        sessoes = [(nome_da_sessao(s), s) for s in AudioUtilities.GetAllSessions()]
        sessoes = [(n, s) for n, s in sessoes if n]
        if "nome" in d:
            nivel = max(0, min(100, int(d["nivel"]))) / 100
            for n, s in sessoes:
                if n == d["nome"]:
                    s.SimpleAudioVolume.SetMasterVolume(nivel, None)
        itens = {n: round(s.SimpleAudioVolume.GetMasterVolume() * 100) for n, s in sessoes}
    except Exception:
        return jsonify(msg="Não consegui ler os programas de áudio"), 500
    finally:
        comtypes.CoUninitialize()
    return jsonify(itens=[{"nome": n, "nivel": v} for n, v in sorted(itens.items())])


def abrir_alvo(alvo):
    if alvo.startswith("app:"):
        return abrir_app(alvo[4:].strip())
    os.startfile(alvo)
    return True


def definir_volume(nivel):
    comtypes.CoInitialize()
    try:
        iface = AudioUtilities.GetSpeakers().Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        cast(iface, POINTER(IAudioEndpointVolume)).SetMasterVolumeLevelScalar(
            max(0, min(100, int(nivel))) / 100, None)
    finally:
        comtypes.CoUninitialize()


def abrir_stremio():
    """Tenta instalações conhecidas; nenhum caminho vem do celular."""
    local = os.environ.get("LOCALAPPDATA")
    if local:
        raiz = Path(local)
        candidatos = (
            raiz / "Programs" / "Stremio" / "stremio-shell-ng.exe",
            raiz / "Programs" / "Stremio" / "stremio.exe",
            raiz / "Smart Code ltd" / "Stremio-4" / "stremio.exe",
        )
        for executavel in candidatos:
            if executavel.is_file():
                try:
                    subprocess.Popen([str(executavel)], cwd=str(executavel.parent))
                    return True
                except OSError:
                    continue
    return abrir_app("Stremio")


def ajustar_samsung_filme():
    """Aplica somente o preset fixo da tela Samsung deste setup."""
    import monitores
    try:
        telas = [t for t in monitores.listar()
                 if t["nome"] == "Samsung (via conversor VGA)" and t["tipo"] == "software"]
        if len(telas) != 1:
            return "Samsung não identificado; brilho dos monitores mantido."
        monitores.ajustar({"id": telas[0]["id"], "tipo": "software", "nivel": 50})
        return "Samsung em 50% por software; brilho do Haiz mantido."
    except Exception:
        app.logger.exception("Falha ao aplicar brilho do Samsung no modo Filme")
        return "Não consegui ajustar o Samsung; use os controles na aba PC."


def iniciar_filme():
    """Abre o Stremio e pede o fechamento normal das janelas permitidas."""
    import ctypes
    from ctypes import wintypes

    # Lista fixa: nunca recebe nomes de processos enviados pelo celular.
    permitidos = {"firefox.exe", "spotify.exe", "chatgpt.exe", "claude.exe"}
    usuario = ctypes.WinDLL("user32", use_last_error=True)
    callback_tipo = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    usuario.EnumWindows.argtypes = [callback_tipo, wintypes.LPARAM]
    usuario.EnumWindows.restype = wintypes.BOOL
    usuario.IsWindowVisible.argtypes = [wintypes.HWND]
    usuario.IsWindowVisible.restype = wintypes.BOOL
    usuario.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    usuario.GetWindowTextLengthW.restype = ctypes.c_int
    usuario.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    usuario.GetWindowThreadProcessId.restype = wintypes.DWORD
    usuario.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    usuario.PostMessageW.restype = wintypes.BOOL

    # Se não encontrar o Stremio, não fecha nenhuma janela.
    if not abrir_stremio():
        return jsonify(msg="Não consegui abrir o Stremio. Confira a instalação no PC; nenhuma janela foi fechada."), 404

    @callback_tipo
    def visitar(janela, parametro):
        if not usuario.IsWindowVisible(janela) or not usuario.GetWindowTextLengthW(janela):
            return True
        pid = wintypes.DWORD()
        usuario.GetWindowThreadProcessId(janela, ctypes.byref(pid))
        try:
            if psutil.Process(pid.value).name().lower() in permitidos:
                # WM_CLOSE respeita os avisos de trabalho não salvo do programa.
                usuario.PostMessageW(janela, 0x0010, 0, 0)
        except (psutil.Error, OSError):
            pass
        return True

    if not usuario.EnumWindows(visitar, 0):
        return jsonify(msg="Stremio iniciado, mas não consegui listar as janelas do Windows."), 500
    brilho_filme = ajustar_samsung_filme()
    return jsonify(msg="Stremio iniciado. Fechamento solicitado às janelas de Firefox, Spotify, ChatGPT e Claude; volume mantido. " + brilho_filme)


def executar_modo(passos):
    for p in passos:
        try:
            if "abrir" in p:
                abrir_alvo(p["abrir"])
            elif "volume" in p:
                definir_volume(p["volume"])
            elif "esperar" in p:
                time.sleep(min(float(p["esperar"]), 30))
            elif "desligar_em" in p:
                subprocess.Popen(["shutdown", "/s", "/t", str(int(p["desligar_em"]) * 60)])
        except Exception:
            pass


def ler_modos():
    try:
        return json.loads((BASE / "modos.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


@app.post("/api/modos")
def lista_modos():
    return jsonify(itens=[m["nome"] for m in ler_modos()])


@app.post("/api/modo")
def rodar_modo():
    i = (request.get_json(silent=True) or {}).get("i")
    lista = ler_modos()
    if not isinstance(i, int) or not 0 <= i < len(lista):
        return jsonify(msg="Modo inválido"), 400
    if lista[i].get("acao") == "cinema":
        try:
            return iniciar_filme()
        except Exception:
            app.logger.exception("Falha ao executar o modo Filme")
            return jsonify(msg="Falha no modo Filme. Confira o erro na janela do servidor."), 500
    threading.Thread(target=executar_modo, args=(lista[i].get("passos", []),), daemon=True).start()
    return jsonify(msg=f"Modo {lista[i]['nome']} ativado")


def powershell(cmd):
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + cmd],
        capture_output=True, text=True, encoding="utf-8", timeout=25,
        creationflags=subprocess.CREATE_NO_WINDOW)


def listar_saidas():
    r = powershell("Get-AudioDevice -List | Where-Object {$_.Type -eq 'Playback'} | "
                   "Select-Object Name,ID,Default | ConvertTo-Json -Compress")
    dados = json.loads(r.stdout)
    return [dados] if isinstance(dados, dict) else dados


@app.post("/api/saidas")
def saidas():
    try:
        lista = listar_saidas()
        escolhido = (request.get_json(silent=True) or {}).get("id")
        if escolhido:
            if escolhido not in [d["ID"] for d in lista]:  # só aceita IDs da própria lista
                return jsonify(msg="Saída desconhecida"), 400
            powershell(f"Set-AudioDevice -ID '{escolhido}' | Out-Null")
            lista = listar_saidas()
    except Exception:
        return jsonify(msg="Instale o módulo AudioDeviceCmdlets (veja o LEIAME)"), 500
    return jsonify(itens=[{"nome": d["Name"], "id": d["ID"], "atual": bool(d["Default"])} for d in lista])


async def _tocando(com_capa):
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Gerente
    gerente = await Gerente.request_async()
    sessao = gerente.get_current_session()
    if sessao is None:
        return {"titulo": "", "artista": "", "tocando": False}
    info = await sessao.try_get_media_properties_async()
    resp = {"titulo": info.title, "artista": info.artist,
            "tocando": sessao.get_playback_info().playback_status == 4}
    if com_capa and info.thumbnail:
        from winrt.windows.storage.streams import Buffer, DataReader, InputStreamOptions
        fluxo = await info.thumbnail.open_read_async()
        buf = Buffer(fluxo.size)
        await fluxo.read_async(buf, buf.capacity, InputStreamOptions.READ_AHEAD)
        bruto = bytearray(buf.length)
        DataReader.from_buffer(buf).read_bytes(bruto)
        resp["capa"] = base64.b64encode(bytes(bruto)).decode()
    return resp


@app.post("/api/tocando")
def tocando():
    try:
        return jsonify(asyncio.run(_tocando(bool((request.get_json(silent=True) or {}).get("capa")))))
    except Exception:
        return jsonify(msg="Instale os pacotes winrt (veja o LEIAME)"), 500



# Arquivos são apenas salvos: nunca abertos ou executados pelo servidor.
LIMITE_ARQUIVO = 100 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = LIMITE_ARQUIVO + 1024 * 1024
PASTA_RECEBIDOS = Path.home() / "Downloads" / "Recebidos do celular"
EXTENSOES_RECEBIDAS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".avif", ".bmp",
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".3gp",
    ".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac", ".opus",
    ".pdf", ".txt", ".csv", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp", ".epub", ".zip", ".rar", ".7z"
})


@app.errorhandler(413)
def arquivo_grande(erro):
    return jsonify(msg="Arquivo muito grande. O limite é 100 MB por arquivo."), 413


@app.post("/api/arquivo")
def receber_arquivo():
    from werkzeug.utils import secure_filename
    arquivos = request.files.getlist("arquivo")
    if len(arquivos) != 1 or not arquivos[0].filename:
        return jsonify(msg="Selecione um arquivo por envio."), 400
    arquivo = arquivos[0]
    extensao = Path(arquivo.filename).suffix.lower()
    if extensao not in EXTENSOES_RECEBIDAS:
        return jsonify(msg="Formato não permitido. Envie fotos, vídeos, áudio, documentos ou arquivos compactados."), 400
    # Remove caminhos e caracteres especiais; sufixo aleatório evita sobrescrita.
    nome = secure_filename(arquivo.filename.replace("\\", "/").split("/")[-1])
    radical = Path(nome).stem[:100] or "arquivo"
    destino = None
    criado = False
    try:
        PASTA_RECEBIDOS.mkdir(parents=True, exist_ok=True)
        destino = PASTA_RECEBIDOS / ("recebido-" + radical + "-" + secrets.token_hex(6) + extensao)
        with destino.open("xb") as saida_arquivo:
            criado = True
            tamanho = 0
            while bloco := arquivo.stream.read(1024 * 1024):
                tamanho += len(bloco)
                if tamanho > LIMITE_ARQUIVO:
                    raise ValueError("limite")
                saida_arquivo.write(bloco)
        return jsonify(msg="Arquivo salvo em Downloads / Recebidos do celular.", nome=destino.name), 201
    except (OSError, ValueError) as erro:
        if criado:
            try:
                destino.unlink(missing_ok=True)
            except OSError:
                pass
        if isinstance(erro, ValueError):
            return jsonify(msg="O limite é 100 MB por arquivo."), 413
        return jsonify(msg="Não foi possível salvar. Confira o espaço em disco e as permissões da pasta."), 500



@app.post("/api/monitores")
def lista_monitores():
    import monitores
    try:
        return jsonify(itens=monitores.listar())
    except Exception:
        app.logger.exception("Falha ao consultar os monitores")
        return jsonify(msg="Não consegui consultar os monitores. Tente atualizar a lista."), 500


@app.post("/api/monitor_brilho")
def brilho_monitor():
    import monitores
    try:
        itens = monitores.ajustar(request.get_json(silent=True))
        return jsonify(msg="Monitor ajustado", itens=itens)
    except ValueError as erro:
        return jsonify(msg=str(erro)), 400
    except Exception:
        app.logger.exception("Falha ao ajustar o monitor")
        return jsonify(msg="Não consegui ajustar o monitor. Atualize a lista e tente novamente."), 500


@app.post("/api/monitores_limpar")
def limpar_escurecimento():
    import monitores
    try:
        monitores.limpar()
        return jsonify(msg="Escurecimento por software removido; brilho real mantido.")
    except Exception:
        return jsonify(msg="Não consegui remover o escurecimento. Reinicie o servidor."), 500


def garantir_instancia_unica():
    """Impede cópias simultâneas do servidor na mesma sessão do Windows."""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    ctypes.set_last_error(0)
    identificador = kernel.CreateMutexW(None, False, "Local\\ControlePCServidorPorta5000")
    erro = ctypes.get_last_error()
    if not identificador:
        raise OSError(erro, "Não foi possível reservar a instância do servidor")
    if erro == 183:  # ERROR_ALREADY_EXISTS
        kernel.CloseHandle(identificador)
        return None
    # O Windows libera o identificador ao encerrar este processo.
    return identificador


if __name__ == "__main__":
    instancia_servidor = garantir_instancia_unica()
    if instancia_servidor is None:
        print("O servidor já está em execução. Para atualizar, use parar.bat antes de iniciar.bat.")
        raise SystemExit(0)
    print(f"\nAbra no celular: http://{ip_local()}:{PORTA}")
    print(f"Token: {TOKEN}\n")
    # Prepara os atalhos da Store sem atrasar a abertura do servidor.
    threading.Thread(target=carregar_apps_uwp, daemon=True).start()
    app.run(host="0.0.0.0", port=PORTA)
