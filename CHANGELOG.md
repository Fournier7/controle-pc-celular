# Histórico de mudanças

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
