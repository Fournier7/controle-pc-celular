"""Tela remota do monitor principal, servida pela mesma porta do Flask."""
import asyncio
import ctypes
from ctypes import wintypes
import io
import json
import secrets
import threading
import time
import string

import mss
import uvicorn
from a2wsgi import WSGIMiddleware
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from flask import jsonify, request
from PIL import Image, ImageDraw
from pynput.keyboard import Controller, Key, KeyCode
from pynput.mouse import Button, Controller as Mouse

TECLAS = {
    "Enter": Key.enter, "Escape": Key.esc, "Backspace": Key.backspace,
    "Tab": Key.tab, "Space": Key.space, "Delete": Key.delete,
    "ArrowUp": Key.up, "ArrowDown": Key.down,
    "ArrowLeft": Key.left, "ArrowRight": Key.right,
    "ShiftLeft": Key.shift_l, "ShiftRight": Key.shift_r,
    "ControlLeft": Key.ctrl_l, "ControlRight": Key.ctrl_r,
    "AltLeft": Key.alt_l, "AltRight": Key.alt_r,
    **{f"Key{letra}": KeyCode.from_vk(ord(letra)) for letra in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
    **{f"Digit{digito}": KeyCode.from_vk(ord(digito)) for digito in "0123456789"},
}
BOTOES = {"esquerdo": Button.left, "direito": Button.right}
CARACTERES = frozenset(
    string.ascii_letters + string.digits + string.punctuation + " "
    + "áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ"
)


class InfoJanela(ctypes.Structure):
    _fields_ = [
        ("tamanho", wintypes.DWORD), ("flags", wintypes.DWORD),
        ("ativa", wintypes.HWND), ("foco", wintypes.HWND),
        ("captura", wintypes.HWND), ("menu", wintypes.HWND),
        ("movimento", wintypes.HWND), ("cursor_texto", wintypes.HWND),
        ("area_cursor", wintypes.RECT),
    ]


ler_info_janela = ctypes.windll.user32.GetGUIThreadInfo
ler_info_janela.argtypes = [wintypes.DWORD, ctypes.POINTER(InfoJanela)]
ler_info_janela.restype = wintypes.BOOL


def ha_cursor_texto():
    info = InfoJanela()
    info.tamanho = ctypes.sizeof(info)
    return bool(ler_info_janela(0, ctypes.byref(info))
                and info.foco and info.cursor_texto and not info.flags & 0x1E)


def capturar():
    with mss.mss() as captura:
        telas = captura.monitors[1:]
        if not telas:
            raise RuntimeError("Nenhum monitor disponível")
        tela = next((t for t in telas if t["left"] == t["top"] == 0), telas[0])
        quadro = captura.grab(tela)
        imagem = Image.frombytes("RGB", quadro.size, quadro.bgra, "raw", "BGRX")
        imagem.thumbnail((1920, 1920), Image.Resampling.BICUBIC)
        cursor = wintypes.POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor)):
            x = (cursor.x - tela["left"]) * imagem.width // tela["width"]
            y = (cursor.y - tela["top"]) * imagem.height // tela["height"]
            if 0 <= x < imagem.width and 0 <= y < imagem.height:
                ImageDraw.Draw(imagem).polygon(
                    [(x, y), (x, y + 16), (x + 4, y + 12), (x + 7, y + 18),
                     (x + 10, y + 16), (x + 7, y + 10), (x + 13, y + 10)],
                    fill="white", outline="black",
                )
        dados = io.BytesIO()
        imagem.save(dados, "JPEG", quality=80, subsampling=0)
        return tela, dados.getvalue()


def aplicar_entrada(dados, tela, mouse, teclado, botoes, teclas):
    acao = dados.get("acao")
    if acao == "soltar":
        for botao in tuple(botoes):
            mouse.release(botao)
            botoes.remove(botao)
        for tecla in tuple(teclas):
            teclado.release(tecla)
            teclas.remove(tecla)
    elif acao in ("mover", "pressionar", "liberar", "clicar"):
        botao = BOTOES.get(dados.get("botao"))
        if acao != "mover" and botao is None:
            return
        x, y = dados.get("x"), dados.get("y")
        if any(type(v) not in (int, float) or not 0 <= v <= 1 for v in (x, y)):
            return
        mouse.position = (
            tela["left"] + round(x * (tela["width"] - 1)),
            tela["top"] + round(y * (tela["height"] - 1)),
        )
        if acao == "pressionar" and botao not in botoes:
            mouse.press(botao)
            botoes.add(botao)
        elif acao == "liberar" and botao in botoes:
            mouse.release(botao)
            botoes.remove(botao)
        elif acao == "clicar":
            mouse.click(botao)
    elif acao == "mover_relativo":
        dx, dy = dados.get("dx"), dados.get("dy")
        if any(type(v) not in (int, float) or not -1 <= v <= 1 for v in (dx, dy)):
            return
        x, y = mouse.position
        esquerda, topo = tela["left"], tela["top"]
        mouse.position = (
            max(esquerda, min(esquerda + tela["width"] - 1, x + round(dx * tela["width"]))),
            max(topo, min(topo + tela["height"] - 1, y + round(dy * tela["height"]))),
        )
    elif acao == "clicar_cursor":
        botao = BOTOES.get(dados.get("botao"))
        x, y = mouse.position
        if (botao is not None and tela["left"] <= x < tela["left"] + tela["width"]
                and tela["top"] <= y < tela["top"] + tela["height"]):
            mouse.click(botao)
            return True
    elif acao == "rolar":
        passos = dados.get("passos")
        if type(passos) is int and -3 <= passos <= 3:
            mouse.scroll(0, passos)
    elif acao == "texto":
        texto = dados.get("texto")
        if isinstance(texto, str) and 0 < len(texto) <= 80:
            teclado.type("".join(c for c in texto if c in CARACTERES))
    elif acao in ("tecla", "soltar_tecla", "tocar_tecla"):
        tecla = TECLAS.get(dados.get("codigo"))
        if tecla is None:
            return
        if acao == "tecla" and tecla not in teclas:
            teclado.press(tecla)
            teclas.add(tecla)
        elif acao == "soltar_tecla" and tecla in teclas:
            teclado.release(tecla)
            teclas.remove(tecla)
        elif acao == "tocar_tecla" and tecla not in teclas:
            teclado.tap(tecla)


def criar_servidor(flask_app):
    servidor = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    bilhetes = {}
    trava = threading.Lock()
    sessao = asyncio.Lock()

    @flask_app.post("/api/desktop/sessao")
    def criar_bilhete():
        agora = time.monotonic()
        with trava:
            for chave in list(bilhetes):
                if bilhetes[chave][1] <= agora:
                    del bilhetes[chave]
            if len(bilhetes) >= 32:
                return jsonify(msg="Aguarde alguns segundos e tente novamente"), 429
            bilhete = secrets.token_urlsafe(24)
            bilhetes[bilhete] = (request.remote_addr, agora + 15)
        resposta = jsonify(bilhete=bilhete)
        resposta.headers["Cache-Control"] = "no-store"
        return resposta

    @servidor.websocket("/desktop/ws")
    async def desktop(ws: WebSocket):
        esquema = "https" if ws.url.scheme == "wss" else "http"
        if ws.headers.get("origin") != f"{esquema}://{ws.headers.get('host')}":
            await ws.close(code=1008)
            return
        await ws.accept()
        try:
            bilhete = await asyncio.wait_for(ws.receive_text(), 4)
            with trava:
                registro = bilhetes.pop(bilhete, None)
            if not registro or registro[0] != ws.client.host or registro[1] <= time.monotonic():
                await ws.close(code=1008)
                return
            if sessao.locked():
                await ws.close(code=1013)
                return
            async with sessao:
                await transmitir(ws)
        except WebSocketDisconnect:
            pass
        except (asyncio.TimeoutError, ValueError, TypeError, KeyError):
            await ws.close(code=1008)

    servidor.mount("/", WSGIMiddleware(flask_app))
    return servidor


async def transmitir(ws):
    mouse, teclado = Mouse(), Controller()
    botoes, teclas = set(), set()
    tela = None
    proximo = 0
    pedido_quadro = asyncio.Event()

    async def enviar_quadros():
        nonlocal tela, proximo
        try:
            while True:
                await pedido_quadro.wait()
                pedido_quadro.clear()
                await asyncio.sleep(max(0, proximo - time.monotonic()))
                proximo = time.monotonic() + 1 / 20
                tela, imagem = await asyncio.to_thread(capturar)
                await asyncio.wait_for(ws.send_bytes(imagem), 5)
        except WebSocketDisconnect:
            return
        except Exception:
            await ws.close(code=1011)

    tarefa_quadros = asyncio.create_task(enviar_quadros())
    janela = time.monotonic()
    mensagens = 0
    try:
        while True:
            texto = await asyncio.wait_for(ws.receive_text(), 20)
            agora = time.monotonic()
            if agora - janela >= 1:
                janela, mensagens = agora, 0
            mensagens += 1
            if mensagens > 180:
                await ws.close(code=1008)
                return
            if texto == "quadro":
                pedido_quadro.set()
            elif tela:
                dados = json.loads(texto)
                if isinstance(dados, dict):
                    toque_texto = (
                        dados.get("acao") == "liberar"
                        and dados.get("botao") == "esquerdo"
                        and dados.get("verificarTeclado") is True
                        and Button.left in botoes
                    )
                    clicou = aplicar_entrada(dados, tela, mouse, teclado, botoes, teclas)
                    clique_texto = clicou and dados.get("botao") == "esquerdo"
                    if clique_texto or (toque_texto and Button.left not in botoes):
                        await asyncio.sleep(.05)
                        await asyncio.wait_for(ws.send_json({"teclado": ha_cursor_texto()}), 5)
    finally:
        tarefa_quadros.cancel()
        await asyncio.gather(tarefa_quadros, return_exceptions=True)
        aplicar_entrada({"acao": "soltar"}, tela, mouse, teclado, botoes, teclas)


def executar(flask_app, porta):
    uvicorn.run(
        criar_servidor(flask_app), host="0.0.0.0", port=porta,
        proxy_headers=False, access_log=False, ws="websockets",
        ws_max_size=1024, ws_max_queue=16, ws_per_message_deflate=False,
    )
