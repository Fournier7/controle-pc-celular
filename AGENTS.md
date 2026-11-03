# AGENTS.md

## Objetivo
Controlar um PC com Windows pelo celular, na mesma rede Wi-Fi. Um servidor Flask (pasta `servidor/`) executa as ações no PC, a interface web (`servidor/index.html`) é servida por ele, e um app Android simples (`android/`, WebView) só abre essa interface.

## Como rodar
- PC (Windows 10/11, Python 3.10+): `cd servidor`, `pip install -r requirements.txt`, `python app.py`. O terminal mostra o endereço (porta 5000) e o token.
- Verificar sintaxe: `python -m py_compile servidor/app.py`.
- Recursos opcionais: pacotes `winrt-*` (tocando agora) e módulo PowerShell `AudioDeviceCmdlets` (saída de áudio).
- Android: abrir `android/` no Android Studio e gerar o APK debug.

## Estilo de código
- Python simples e legível, nomes e comentários em português, funções curtas, uma rota por ação em `app.py`.
- JavaScript puro, sem frameworks nem etapa de build. CSS com variáveis em `:root`.
- Não adicionar dependências sem avisar e explicar o motivo.
- Arquivos `.bat` e `.vbs` com final de linha CRLF.

## Regras
- Manter a proteção de instância única no início do servidor; para carregar mudanças no Python, parar a instância antiga antes de iniciar a nova.
- Interface atual: grafite e azul, abas Início, Controle, Arquivos e Mais. Vermelho reservado a ações de risco.
- Upload autorizado pelo usuário: POST autenticado, até 100 MB por arquivo, extensões em lista fechada, destino fixo Downloads / Recebidos do celular. Nunca abrir ou executar arquivos recebidos nem aceitar caminhos do celular.
- Modo Filme: abrir Stremio, preservar volume e pedir fechamento normal somente de janelas visíveis de Firefox, Spotify, ChatGPT e Claude. Sem confirmação adicional no celular. Não encerrar outros processos.
- Não apagar nem renomear arquivos sem avisar antes.
- Explicar as mudanças de forma simples: o usuário é iniciante. Responder em português do Brasil.
- Nunca incluir `token.txt`, tokens, senhas, e-mails ou IPs reais no código, nos commits ou nos exemplos.
- Toda rota nova usa POST, passa pelo `before_request` (token e rede local) e só executa ações de listas fechadas. Nunca executar comando, caminho ou texto vindo do celular sem validar contra uma lista.
- Atalhos de letra com `vk("x")` (código virtual) e sem teclas F, porque o teclado do usuário é 60%.
- Só Windows. O servidor escuta em `0.0.0.0:5000` e a porta nunca deve ser exposta na internet.
- Mudou `app.py`? Avisar que precisa reiniciar o servidor. Mudou só `index.html`, `atalhos.json` ou `modos.json`? Basta recarregar a página.
- Mudou algo em `android/`? Avisar que é preciso gerar um APK novo.
