import ast
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from concurrent.futures import ThreadPoolExecutor

arvore = ast.parse((Path(__file__).resolve().parents[1] / 'servidor' / 'app.py').read_text(encoding='utf-8'))
nomes = {'carregar_apps_uwp', 'abrir_app_uwp'}
nos = [n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name in nomes]
subprocess = SimpleNamespace(CREATE_NO_WINDOW=0, TimeoutExpired=TimeoutError,
    run=Mock(return_value=SimpleNamespace(returncode=0, stdout=json.dumps([
        {'Name':'WhatsApp', 'AppID':'app-teste'}, {'Name':'Outro app', 'AppID':'outro-teste'}]))),
    Popen=Mock())
escopo = dict(globals(), CATALOGO_APPS=None, REPETIR_BUSCA_APPS_EM=0, TRAVA_APPS=threading.Lock(), APPS={})
exec(compile(ast.Module(body=nos, type_ignores=[]), '<cache-isolado>', 'exec'), escopo)
with ThreadPoolExecutor(max_workers=4) as executor:
    list(executor.map(lambda _: escopo['carregar_apps_uwp'](), range(8)))
assert subprocess.run.call_count == 1
assert escopo['abrir_app_uwp']('WhatsApp')
assert escopo['abrir_app_uwp']('Outro app')
assert not escopo['abrir_app_uwp']('Não instalado')
assert subprocess.run.call_count == 1
assert subprocess.Popen.call_count == 2
assert subprocess.Popen.call_args.args[0] == ['explorer.exe', 'shell:AppsFolder\\outro-teste']
escopo['CATALOGO_APPS'] = None
subprocess.run.return_value = SimpleNamespace(returncode=1, stdout='')
assert escopo['carregar_apps_uwp']() == []
assert escopo['carregar_apps_uwp']() == []
assert subprocess.run.call_count == 2, 'Falhas devem ter intervalo antes de nova tentativa'
print('OK: consulta única, concorrência, busca por nome, apps ausentes e intervalo após falha. Nenhum programa real foi aberto.')

