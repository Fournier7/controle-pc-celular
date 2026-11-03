import ast
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

arquivo = Path(__file__).resolve().parents[1] / 'servidor' / 'app.py'
arvore = ast.parse(arquivo.read_text(encoding='utf-8'))
funcao = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == 'abrir_stremio')
with tempfile.TemporaryDirectory() as pasta:
    subprocess = SimpleNamespace(Popen=Mock())
    fallback = Mock(return_value=False)
    escopo = dict(Path=Path, os=SimpleNamespace(environ={'LOCALAPPDATA': pasta}), subprocess=subprocess, abrir_app=fallback)
    exec(compile(ast.Module(body=[funcao], type_ignores=[]), '<abrir-stremio>', 'exec'), escopo)
    assert not escopo['abrir_stremio']()
    fallback.assert_called_once_with('Stremio')
    executavel = Path(pasta) / 'Programs' / 'Stremio' / 'stremio-shell-ng.exe'
    executavel.parent.mkdir(parents=True)
    executavel.touch()
    fallback.reset_mock()
    assert escopo['abrir_stremio']()
    subprocess.Popen.assert_called_once_with([str(executavel)], cwd=str(executavel.parent))
    fallback.assert_not_called()
    subprocess.Popen.side_effect = OSError('falha simulada')
    assert not escopo['abrir_stremio']()
    fallback.assert_called_once_with('Stremio')
codigo = arquivo.read_text(encoding='utf-8')
assert 'permitidos = {"firefox.exe", "spotify.exe", "chatgpt.exe", "claude.exe"}' in codigo
html = arquivo.with_name('index.html').read_text(encoding='utf-8')
assert '!confirm(' not in html
assert "hasAttribute('data-confirmar')" in html
print('OK: instalação local, diretório correto, busca alternativa e falha de abertura. Confirmação removida só do modo Filme; nenhum programa real foi aberto ou fechado.')
