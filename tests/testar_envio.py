import ast
import hmac
import io
import ipaddress
import secrets
import tempfile
import time
from pathlib import Path
from flask import Flask, request, jsonify, abort

# Extrai as funções reais sem importar controladores Windows ou carregar tokens locais.
arvore = ast.parse((Path(__file__).resolve().parents[1] / 'servidor' / 'app.py').read_text(encoding='utf-8'))
nomes = {'proteger', 'arquivo_grande', 'receber_arquivo'}
constantes = {'LIMITE_ARQUIVO', 'EXTENSOES_RECEBIDAS'}
nos = [n for n in arvore.body if
       isinstance(n, ast.FunctionDef) and n.name in nomes or
       isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constantes for t in n.targets)]
app = Flask(__name__)
escopo = dict(globals(), app=app, TOKEN='credencial-local-de-teste', falhas={},
              REDE_TAILSCALE=ipaddress.ip_network('100.64.0.0/10'))
exec(compile(ast.Module(body=nos, type_ignores=[]), '<rotas-reais>', 'exec'), escopo)
with tempfile.TemporaryDirectory() as temporario:
    pasta = Path(temporario)
    escopo['PASTA_RECEBIDOS'] = pasta
    cliente = app.test_client()
    cabecalho = {'X-Token': escopo['TOKEN']}
    def enviar(nome, conteudo=b'conteudo', headers=cabecalho):
        return cliente.post('/api/arquivo', data={'arquivo': (io.BytesIO(conteudo), nome)}, headers=headers)
    assert enviar('foto.jpg', headers={}).status_code == 401
    assert not list(pasta.iterdir())
    assert enviar('programa.exe').status_code == 400
    assert cliente.post('/api/arquivo', headers=cabecalho).status_code == 400
    assert cliente.get('/api/arquivo', headers=cabecalho).status_code == 405
    for nome in ('foto.jpg', 'foto.jpg', '../../foto.jpg', r'..\foto.jpg', 'CON.txt'):
        resposta = enviar(nome)
        assert resposta.status_code == 201, resposta.json
        destino = pasta / resposta.json['nome']
        assert destino.parent == pasta and destino.read_bytes() == b'conteudo'
    assert len(list(pasta.iterdir())) == 5
    escopo['LIMITE_ARQUIVO'] = 3
    assert enviar('grande.pdf', b'1234').status_code == 413
    assert len(list(pasta.iterdir())) == 5, 'Arquivo parcial deve ser removido'
    app.config['MAX_CONTENT_LENGTH'] = 10
    assert enviar('grande.pdf').status_code == 413
print('OK: autenticação, POST, formatos, caminhos, duplicatas, limite e remoção de envio parcial.')
