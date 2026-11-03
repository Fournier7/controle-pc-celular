"""Brilho DDC/CI e escurecimento independente, sem dependências adicionais."""
import atexit
import ctypes
import json
import queue
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

TRAVA = threading.Lock()
NIVEIS_SOFTWARE = {}
PROCESSO = None
RESPOSTAS = None


class Fisico(ctypes.Structure):
    _fields_ = [("handle", wintypes.HANDLE), ("nome", wintypes.WCHAR * 128)]


class Info(ctypes.Structure):
    _fields_ = [("tamanho", wintypes.DWORD), ("area", wintypes.RECT),
                ("trabalho", wintypes.RECT), ("flags", wintypes.DWORD),
                ("dispositivo", wintypes.WCHAR * 32)]


class Dispositivo(ctypes.Structure):
    _fields_ = [("tamanho", wintypes.DWORD), ("nome", wintypes.WCHAR * 32),
                ("descricao", wintypes.WCHAR * 128), ("flags", wintypes.DWORD),
                ("id", wintypes.WCHAR * 128), ("chave", wintypes.WCHAR * 128)]


def bibliotecas():
    usuario = ctypes.WinDLL("user32", use_last_error=True)
    ddc = ctypes.WinDLL("dxva2", use_last_error=True)
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
                                  ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    usuario.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), callback, wintypes.LPARAM]
    usuario.EnumDisplayMonitors.restype = wintypes.BOOL
    usuario.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Info)]
    usuario.GetMonitorInfoW.restype = wintypes.BOOL
    usuario.EnumDisplayDevicesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(Dispositivo), wintypes.DWORD]
    usuario.EnumDisplayDevicesW.restype = wintypes.BOOL
    ddc.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    ddc.GetPhysicalMonitorsFromHMONITOR.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(Fisico)]
    ddc.DestroyPhysicalMonitors.argtypes = [wintypes.DWORD, ctypes.POINTER(Fisico)]
    ddc.GetMonitorBrightness.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.DWORD)] * 3
    ddc.SetMonitorBrightness.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    ddc.SetVCPFeature.argtypes = [wintypes.HANDLE, wintypes.BYTE, wintypes.DWORD]
    ddc.SetVCPFeature.restype = wintypes.BOOL
    ddc.GetVCPFeatureAndVCPFeatureReply.argtypes = [wintypes.HANDLE, wintypes.BYTE,
        ctypes.POINTER(ctypes.c_int), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
    ddc.GetVCPFeatureAndVCPFeatureReply.restype = wintypes.BOOL
    for nome in ("GetNumberOfPhysicalMonitorsFromHMONITOR", "GetPhysicalMonitorsFromHMONITOR",
                 "DestroyPhysicalMonitors", "GetMonitorBrightness", "SetMonitorBrightness"):
        getattr(ddc, nome).restype = wintypes.BOOL
    return usuario, ddc, callback


def ler_telas(acao=None):
    usuario, ddc, callback = bibliotecas()
    itens, erros = [], []

    @callback
    def visitar(handle, contexto, retangulo, parametro):
        fisicos = None
        quantidade = wintypes.DWORD()
        try:
            info = Info(); info.tamanho = ctypes.sizeof(info)
            if not usuario.GetMonitorInfoW(handle, ctypes.byref(info)):
                raise OSError("Não consegui identificar uma tela")
            dispositivo = Dispositivo(); dispositivo.tamanho = ctypes.sizeof(dispositivo)
            codigo = ""
            if usuario.EnumDisplayDevicesW(info.dispositivo, 0, ctypes.byref(dispositivo), 0):
                partes = dispositivo.id.split("\\")
                codigo = partes[1] if len(partes) > 1 else ""
            nome = {"LHC90D2": "Haiz HZ-LM25GM", "RGT1252": "Samsung (via conversor VGA)"}.get(codigo, dispositivo.descricao or "Monitor")
            item = {"id": info.dispositivo, "nome": nome, "tipo": "software",
                    "nivel": NIVEIS_SOFTWARE.get(info.dispositivo, 100)}
            minimo, atual, maximo = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
            brilho = None
            suporta_brilho = False
            if ddc.GetNumberOfPhysicalMonitorsFromHMONITOR(handle, ctypes.byref(quantidade)) and quantidade.value == 1:
                fisicos = (Fisico * quantidade.value)()
                if ddc.GetPhysicalMonitorsFromHMONITOR(handle, quantidade, fisicos):
                    tipo_leitura = ctypes.c_int()
                    if ddc.GetMonitorBrightness(fisicos[0].handle, ctypes.byref(minimo), ctypes.byref(atual), ctypes.byref(maximo)) and maximo.value > minimo.value:
                        brilho = fisicos[0].handle
                        suporta_brilho = True
                    atual_vcp, maximo_vcp = wintypes.DWORD(), wintypes.DWORD()
                    if ddc.GetVCPFeatureAndVCPFeatureReply(fisicos[0].handle, 0x10, ctypes.byref(tipo_leitura), ctypes.byref(atual_vcp), ctypes.byref(maximo_vcp)) and maximo_vcp.value > 0:
                        brilho = fisicos[0].handle
                        suporta_brilho = True
                        minimo.value, atual.value, maximo.value = 0, atual_vcp.value, maximo_vcp.value
                    if suporta_brilho:
                        item.update(tipo="real", nivel=round((atual.value - minimo.value) * 100 / (maximo.value - minimo.value)))
                else:
                    fisicos = None
            if acao and item["id"] == acao["id"]:
                nivel = acao["nivel"]
                if item["tipo"] != acao["tipo"]:
                    raise ValueError("A conexão do monitor mudou. Atualize a lista.")
                if suporta_brilho:
                    valor = minimo.value + round((maximo.value - minimo.value) * nivel / 100)
                    if not ddc.SetVCPFeature(brilho, 0x10, valor):
                        raise OSError("O monitor recusou a alteração do brilho")
                    tipo_vcp, confirmado, limite_vcp = ctypes.c_int(), wintypes.DWORD(), wintypes.DWORD()
                    for tentativa in range(5):
                        time.sleep(.1)
                        if ddc.GetVCPFeatureAndVCPFeatureReply(brilho, 0x10, ctypes.byref(tipo_vcp), ctypes.byref(confirmado), ctypes.byref(limite_vcp)) and confirmado.value == valor:
                            break
                    else:
                        raise OSError("O monitor não confirmou a alteração do brilho")
                else:
                    area = info.area
                    comando_software({"acao": "ajustar", "tela": item["id"], "nivel": nivel,
                        "area": [area.left, area.top, area.right - area.left, area.bottom - area.top]})
                    NIVEIS_SOFTWARE[item["id"]] = nivel
                item["nivel"] = nivel
            itens.append(item)
        except Exception as erro:
            erros.append(erro)
        finally:
            if fisicos is not None:
                ddc.DestroyPhysicalMonitors(quantidade, fisicos)
        return True

    if not usuario.EnumDisplayMonitors(None, None, visitar, 0):
        raise OSError("Não consegui enumerar os monitores")
    if erros:
        raise erros[0]
    if acao and not any(i["id"] == acao["id"] for i in itens):
        raise ValueError("Monitor desconectado. Atualize a lista.")
    return itens


def comando_software(comando):
    global PROCESSO, RESPOSTAS
    if PROCESSO is None or PROCESSO.poll() is not None:
        NIVEIS_SOFTWARE.clear()
        processo = subprocess.Popen([sys.executable, str(Path(__file__).with_name("escurecer.py"))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW)
        respostas = queue.Queue()
        def ler():
            try:
                for linha in processo.stdout:
                    respostas.put(json.loads(linha))
            finally:
                respostas.put({"ok": False})
        threading.Thread(target=ler, daemon=True).start()
        PROCESSO, RESPOSTAS = processo, respostas
        try:
            if not respostas.get(timeout=6).get("pronto"):
                raise OSError("Não consegui iniciar o escurecimento")
        except (OSError, queue.Empty):
            encerrar_software()
            raise OSError("Não consegui iniciar o escurecimento")
    try:
        PROCESSO.stdin.write(json.dumps(comando) + "\n")
        PROCESSO.stdin.flush()
        if not RESPOSTAS.get(timeout=4).get("ok"):
            raise OSError("Não consegui ajustar o escurecimento")
    except (OSError, queue.Empty):
        encerrar_software()
        raise OSError("O escurecimento foi removido por falha. Tente novamente.")


def encerrar_software():
    global PROCESSO
    if PROCESSO is not None:
        try:
            PROCESSO.stdin.close()
            PROCESSO.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            PROCESSO.terminate()
        PROCESSO = None
    NIVEIS_SOFTWARE.clear()


def listar():
    with TRAVA:
        if PROCESSO is not None and PROCESSO.poll() is not None:
            NIVEIS_SOFTWARE.clear()
        return ler_telas()


def ajustar(dados):
    if not isinstance(dados, dict) or not isinstance(dados.get("id"), str):
        raise ValueError("Monitor inválido")
    nivel = dados.get("nivel")
    if type(nivel) is not int or not 20 <= nivel <= 100:
        raise ValueError("Escolha um valor entre 20 e 100")
    if dados.get("tipo") not in ("real", "software"):
        raise ValueError("Tipo de controle inválido")
    with TRAVA:
        return ler_telas(dados)


def limpar():
    with TRAVA:
        encerrar_software()


atexit.register(encerrar_software)
