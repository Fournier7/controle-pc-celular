import ast
import hmac
import ipaddress
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from flask import Flask, jsonify, request, abort

base = Path(__file__).resolve().parents[1] / 'servidor'
sys.path.insert(0, str(base))
import monitores
for dados in (None, [], {}, {'id': 'x', 'tipo': 'software', 'nivel': True},
              {'id': 'x', 'tipo': 'software', 'nivel': 0},
              {'id': 'x', 'tipo': 'software', 'nivel': 101},
              {'id': 'x', 'tipo': 'comando', 'nivel': 60}):
    try:
        monitores.ajustar(dados)
    except ValueError:
        pass
    else:
        raise AssertionError(dados)
falso = SimpleNamespace(listar=Mock(return_value=[]), ajustar=Mock(return_value=[]), limpar=Mock())
sys.modules['monitores'] = falso
arvore = ast.parse((base / 'app.py').read_text(encoding='utf-8'))
nos = [n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name in
       {'proteger', 'lista_monitores', 'brilho_monitor', 'limpar_escurecimento'}]
app = Flask(__name__)
escopo = dict(globals(), app=app, TOKEN='credencial-ficticia-de-teste', falhas={},
              REDE_TAILSCALE=ipaddress.ip_network('100.64.0.0/10'))
exec(compile(ast.Module(body=nos, type_ignores=[]), '<rotas>', 'exec'), escopo)
cliente = app.test_client()
cabecalho = {'X-Token': escopo['TOKEN']}
for rota in ('monitores', 'monitor_brilho', 'monitores_limpar'):
    assert cliente.post('/api/' + rota).status_code == 401
    assert cliente.get('/api/' + rota, headers=cabecalho).status_code == 405
assert cliente.post('/api/monitores', headers=cabecalho, environ_base={'REMOTE_ADDR': '8.8.8.8'}).status_code == 403
assert not falso.listar.called and not falso.ajustar.called and not falso.limpar.called
assert cliente.post('/api/monitores', headers=cabecalho).status_code == 200
falso.ajustar.side_effect = ValueError('Monitor inválido')
assert cliente.post('/api/monitor_brilho', json={}, headers=cabecalho).status_code == 400
assert cliente.post('/api/monitores_limpar', headers=cabecalho).status_code == 200
print('OK: validação de níveis/tipos, token, rede local e POST em todas as rotas; nenhuma ação de hardware nos testes isolados.')
