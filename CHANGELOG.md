# Histórico de mudanças

## 2026-11-11

- Tela ao vivo com toque direto ou touchpad, clique direito, teclado e setas de rolagem na lateral.
- A transmissão abre em tela cheia com o monitor inteiro visível e oferece **Preencher tela** no menu.
- Captura JPEG com até 1920 pixels no lado maior e processamento do cursor em paralelo com o vídeo.
- APK com tela cheia imersiva e suporte ao teclado da transmissão.
- Rolagem mais suave no touchpad da aba Controle, ajustes na estabilidade do áudio e correção do iniciador oculto.
- README e capturas atualizados.

## 2026-11-02

### Monitores, aba PC e preset Filme

- Nova aba PC reúne atalhos de aplicativos e controles dos monitores; as demais funções continuam em Mais.
- Brilho real por DDC/CI com leitura de confirmação, quando suportado, e escurecimento independente por software para telas sem resposta.
- Camada por software sem capturar cliques/foco, removida ao parar o servidor ou usar o botão de remoção.
- Consultas sob demanda e ajustes ao soltar o slider, sem enfileirar comandos a cada movimento.
- Modo Filme ajusta o Samsung identificado deste setup para 50% por software e mantém o brilho do Haiz e o volume.
- Três rotas POST autenticadas com validação de tipo, monitor e nível de 20 a 100.
- Testes isolados dos controles e do preset; cinco capturas atualizadas com dados de demonstração.
- Sem mudança no código Android: o APK existente pode abrir a interface nova com o servidor atualizado.



### Corrigido: modo Filme e reinicialização

- Stremio iniciado primeiro por caminhos locais conhecidos, com diretório de trabalho correto e busca pelo Menu Iniciar como alternativa.
- Retirada a confirmação do modo Filme a pedido do usuário.
- Fechamento normal limitado às janelas visíveis de Firefox, Spotify, ChatGPT e Claude; volume e outros programas preservados.
- Erros do modo Filme passam a produzir uma mensagem na interface e diagnóstico no servidor.
- Acrescentada proteção contra múltiplas instâncias na mesma sessão do Windows. É necessário parar o servidor antigo antes de carregar código atualizado.
- Funcionamento do modo Filme confirmado pelo usuário após encerrar cópias antigas e reiniciar o servidor.
- Testes isolados de abertura do Stremio e proteção de instância única adicionados.



### Otimizado

- Catálogo de aplicativos da Microsoft Store preparado em segundo plano ao iniciar o servidor e reutilizado entre atalhos.
- Consulta única protegida contra requisições concorrentes, com tempo limite e intervalo de nova tentativa após falha.
- Elimina a consulta repetida ao PowerShell ao abrir aplicativos como WhatsApp. O tempo de inicialização do próprio programa ainda depende do Windows.
- Testes isolados do cache aprovados e melhora confirmada pelo usuário no PC.

Para carregar a otimização, reinicie o servidor. Não é necessário gerar ou instalar outro APK. Após instalar novos aplicativos da Store, reinicie o servidor para atualizar o catálogo.


## 2026-11-01

### Adicionado

- Aba Arquivos com seleção múltipla, envio sequencial e progresso por arquivo.
- Recebimento autenticado em Downloads / Recebidos do celular, com limite de 100 MB, lista de extensões e nomes exclusivos.
- Suporte ao seletor nativo de documentos no WebView Android.
- Atalho do WhatsApp e ícones locais nos atalhos de aplicativos.
- Capturas das quatro abas com dados fictícios e documentação atualizada.
- Testes isolados do upload e instruções de desenvolvimento em AGENTS.md.

### Alterado

- Interface completa em grafite e azul, com cartões, navegação com ícones e detalhes tecnológicos.
- Música e volume reunidos; ações de energia abaixo dos controles mais frequentes.
- Explicação dos controles do Discord recolhível.
- Modo Filme abre Stremio sem mudar o volume e pede o fechamento normal das janelas visíveis do Firefox e Spotify. Outros processos são preservados.
- PyCharm removido dos atalhos individuais e mantido no modo Programar.

### Removido da interface

- Seção de atalhos de teclado prontos. A API de combinações permanece para compatibilidade.

### Corrigido

- Confirmação por segundo toque dos botões de energia: o código passa a verificar a presença do atributo `data-confirmar`, mesmo quando está vazio.

### Verificação

- Sintaxe Python e JavaScript verificadas.
- Testes de recebimento de arquivos aprovados.
- APK debug compilado com Gradle 8.7 e JDK 21.
- Renderização da interface em tamanho de celular; dados das capturas são demonstrativos.
