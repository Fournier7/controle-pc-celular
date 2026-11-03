import ast
from pathlib import Path
from unittest.mock import Mock, patch

codigo = (Path(__file__).resolve().parents[1] / 'servidor' / 'app.py').read_text(encoding='utf-8')
arvore = ast.parse(codigo)
funcao = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == 'garantir_instancia_unica')
escopo = {}
exec(compile(ast.Module(body=[funcao], type_ignores=[]), '<instancia>', 'exec'), escopo)
kernel = Mock()
kernel.CreateMutexW.return_value = 123
with patch('ctypes.WinDLL', return_value=kernel, create=True), \
     patch('ctypes.set_last_error', create=True), \
     patch('ctypes.get_last_error', return_value=0, create=True):
    assert escopo['garantir_instancia_unica']() == 123
    kernel.CloseHandle.assert_not_called()
with patch('ctypes.WinDLL', return_value=kernel, create=True), \
     patch('ctypes.set_last_error', create=True), \
     patch('ctypes.get_last_error', return_value=183, create=True):
    assert escopo['garantir_instancia_unica']() is None
    kernel.CloseHandle.assert_called_once_with(123)
kernel.CreateMutexW.return_value = 0
with patch('ctypes.WinDLL', return_value=kernel, create=True), \
     patch('ctypes.set_last_error', create=True), \
     patch('ctypes.get_last_error', return_value=5, create=True):
    try:
        escopo['garantir_instancia_unica']()
    except OSError:
        pass
    else:
        raise AssertionError('Falha na reserva deve impedir a inicialização')
print('OK: instância única, duplicata e falha de reserva; nenhum servidor real foi encerrado.')
