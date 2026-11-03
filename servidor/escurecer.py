"""Camadas pretas por tela; comandos somente do servidor por um pipe local."""
import ctypes
import json
import queue
import sys
import threading
import tkinter as tk
from ctypes import wintypes


def executar():
    usuario = ctypes.WinDLL("user32", use_last_error=True)
    usuario.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    usuario.GetAncestor.restype = wintypes.HWND
    usuario.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    usuario.GetWindowLongW.restype = wintypes.LONG
    usuario.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    usuario.SetWindowLongW.restype = wintypes.LONG
    usuario.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    usuario.SetWindowPos.restype = wintypes.BOOL
    try:
        usuario.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        usuario.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass
    raiz = tk.Tk()
    raiz.withdraw()
    telas = {}
    fila = queue.Queue()

    def responder(**dados):
        print(json.dumps(dados), flush=True)

    def receber():
        try:
            for linha in sys.stdin:
                fila.put(json.loads(linha))
        except (ValueError, OSError):
            pass
        finally:
            fila.put(None)

    def processar():
        try:
            while True:
                comando = fila.get_nowait()
                if comando is None:
                    raiz.destroy()
                    return
                try:
                    if comando.get("acao") == "limpar":
                        for janela in telas.values():
                            janela.destroy()
                        telas.clear()
                    elif comando.get("acao") == "ajustar":
                        tela, nivel, area = comando["tela"], comando["nivel"], comando["area"]
                        if not isinstance(tela, str) or type(nivel) is not int or not 20 <= nivel <= 100:
                            raise ValueError("Comando inválido")
                        if not isinstance(area, list) or len(area) != 4 or any(type(v) is not int for v in area):
                            raise ValueError("Área inválida")
                        if nivel == 100:
                            janela = telas.pop(tela, None)
                            if janela is not None:
                                janela.destroy()
                        else:
                            janela = telas.get(tela)
                            if janela is None:
                                janela = tk.Toplevel(raiz)
                                janela.withdraw()
                                janela.overrideredirect(True)
                                janela.title("Escurecimento do monitor")
                                janela.configure(bg="black")
                                janela.attributes("-alpha", 0)
                                janela.attributes("-topmost", True)
                                janela.update_idletasks()
                                hwnd = usuario.GetAncestor(janela.winfo_id(), 2)
                                estilo = usuario.GetWindowLongW(hwnd, -20)
                                # Clique atravessa; sem foco e sem botão na barra de tarefas.
                                usuario.SetWindowLongW(hwnd, -20, estilo | 0x80000 | 0x20 | 0x80 | 0x08000000)
                                telas[tela] = janela
                            hwnd = usuario.GetAncestor(janela.winfo_id(), 2)
                            x, y, largura, altura = area
                            usuario.SetWindowPos(hwnd, wintypes.HWND(-1), x, y, largura, altura, 0x0010 | 0x0040)
                            janela.attributes("-alpha", (100 - nivel) / 100)
                    else:
                        raise ValueError("Ação inválida")
                    responder(ok=True)
                except Exception:
                    responder(ok=False)
        except queue.Empty:
            pass
        raiz.after(30, processar)

    threading.Thread(target=receber, daemon=True).start()
    raiz.after(30, processar)
    responder(pronto=True)
    raiz.mainloop()


if __name__ == "__main__":
    executar()
