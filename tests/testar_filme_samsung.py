import ast
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

arvore = ast.parse((Path(__file__).resolve().parents[1] / 'servidor' / 'app.py').read_text(encoding='utf-8'))
funcao = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == 'ajustar_samsung_filme')
escopo = {'app': SimpleNamespace(logger=Mock())}
exec(compile(ast.Module(body=[funcao], type_ignores=[]), '<preset>', 'exec'), escopo)
samsung = {'id':'tela-samsung', 'nome':'Samsung (via conversor VGA)', 'tipo':'software'}
haiz = {'id':'tela-haiz', 'nome':'Haiz HZ-LM25GM', 'tipo':'real'}
falso = SimpleNamespace(listar=Mock(return_value=[haiz, samsung]), ajustar=Mock())
with patch.dict(sys.modules, {'monitores': falso}):
    assert '50%' in escopo['ajustar_samsung_filme']()
    falso.ajustar.assert_called_once_with({'id':'tela-samsung', 'tipo':'software', 'nivel':50})
    falso.ajustar.reset_mock()
    for telas in ([haiz], [samsung, samsung]):
        falso.listar.return_value = telas
        assert 'não identificado' in escopo['ajustar_samsung_filme']()
        falso.ajustar.assert_not_called()
    falso.listar.side_effect = OSError('falha simulada')
    assert 'Não consegui' in escopo['ajustar_samsung_filme']()
print('OK: Samsung recebe 50%; nenhuma alteração no Haiz; ausência, duplicidade e falha tratadas. Sem abrir ou fechar programas reais.')
