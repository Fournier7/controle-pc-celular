# Controle do PC pelo celular

Um servidor em Python que roda no PC com Windows e uma interface web para controlá-lo pelo celular, na mesma rede Wi-Fi: desligar, reiniciar, bloquear, teclado, mouse, volume, abrir programas e ver a tela. Acompanha um app Android simples (WebView) que abre a interface em tela cheia.

Projeto pessoal, feito para uso próprio e para aprender. Foi desenvolvido com o auxílio do Claude (Anthropic) como ferramenta de estudo. O guia em `docs/` explica cada parte.

## Funcionalidades

- **Energia:** desligar, reiniciar, bloquear, suspender, desligar depois de X minutos e cancelar.
- **Mídia:** botões de volume, mudo, play/pausa, faixa anterior e próxima, e slider de volume.
- **Teclado:** digitar texto no PC, Enter, Esc, Apagar, Tab, Espaço e setas.
- **Mouse:** touchpad na tela do celular, rolagem e cliques.
- **Atalhos:** abre sites e programas configurados em `servidor/atalhos.json`.
- **Enviar para o PC:** copia (e cola) um texto ou link no PC.
- **Tela do PC:** captura do monitor principal, manual ou automática.
- **Status:** uso de processador, memória e disco.
- **Microfone e Discord:** muta o microfone do Windows e aperta atalhos globais do Discord (mutar e ensurdecer).
- **Atalhos de teclado:** Alt+Tab, área de trabalho, fechar janela, captura de tela, copiar, colar e outros.
- **Modos:** um toque abre vários programas e ajusta o volume (configurados em `servidor/modos.json`).
- **Volume por programa** e **troca da saída de áudio**.
- **Tocando agora:** título, artista e capa da música em reprodução.
- Interface em abas, com tema vermelho e preto.

## Como funciona

```
  CELULAR (app ou site)        Wi-Fi         PC (Windows)
 +---------------------+  POST + token  +---------------------------+
 | interface (HTML/JS) | -------------> | servidor Flask (porta 5000)|
 |                     | <------------- | executa a ação no Windows  |
 +---------------------+     JSON       +---------------------------+
```

O servidor expõe uma pequena API (`/api/...`). A interface é uma página que chama essa API. O app Android só abre essa página.

## Requisitos

- Windows 10 ou 11
- Python 3.10 ou mais novo (marque "Add to PATH" na instalação)
- Celular na mesma rede Wi-Fi do PC

## Como usar

1. Baixe ou clone este repositório e entre na pasta `servidor`.
2. Dê dois cliques em `iniciar.bat`. Na primeira vez ele instala as bibliotecas.
3. Na janela vão aparecer o **endereço** (por exemplo `http://192.168.0.100:5000`) e o **token**.
4. No celular, abra o endereço no navegador e digite o token. O navegador guarda o token.
5. Se o Windows perguntar sobre o Firewall, permita o Python em **redes privadas**.

O token também fica no arquivo `servidor/token.txt` (criado na primeira execução e ignorado pelo Git).

### Rodar escondido e com o Windows

| Arquivo | O que faz |
| --- | --- |
| `iniciar_oculto.vbs` | Liga o servidor sem janela |
| `instalar_inicio.bat` | Liga o servidor sempre que o Windows iniciar |
| `parar.bat` | Desliga o servidor escondido |
| `remover_inicio.bat` | Tira o servidor da inicialização |

Rode `iniciar.bat` uma vez antes, para instalar as bibliotecas. Se algo falhar escondido, use o `iniciar.bat` para ver a mensagem de erro.

### Atalhos

Edite `servidor/atalhos.json`:

```json
[
  {"nome": "YouTube", "alvo": "https://www.youtube.com"},
  {"nome": "Discord", "alvo": "app:Discord"}
]
```

- `https://...` abre o site no navegador padrão.
- `app:Nome` procura o programa pelo nome no Menu Iniciar do Windows e abre.

### Recursos opcionais

Alguns recursos precisam de uma instalação extra, uma vez só:

- **Tocando agora:** `pip install winrt-runtime winrt-Windows.Media.Control winrt-Windows.Storage.Streams winrt-Windows.Foundation winrt-Windows.Foundation.Collections`
- **Troca da saída de áudio:** no PowerShell, `Install-Module -Name AudioDeviceCmdlets -Scope CurrentUser`
- **Botões do Discord:** no Discord, em Atalhos, crie *Alternar mudo* com `Ctrl+Shift+Alt+M` e *Alternar surdo* com `Ctrl+Shift+Alt+D`.

Sem isso, o resto continua funcionando e esses recursos mostram um aviso.

### Ligar o PC (Wake-on-LAN)

O servidor não consegue ligar um PC desligado. Para isso existe o `servidor/ligar.py`, que manda o pacote de Wake-on-LAN:

```
python ligar.py AA:BB:CC:DD:EE:FF
```

Ative o Wake-on-LAN na BIOS e na placa de rede. O comando precisa rodar em um aparelho sempre ligado na mesma rede (um Raspberry Pi, por exemplo). Esta parte ainda não foi testada.

## App Android

A pasta `android/` é um projeto do Android Studio com uma única tela (WebView).

1. Edite `ENDERECO_PADRAO` em `android/app/src/main/java/br/com/controlepc/MainActivity.java` com o endereço do seu PC (também dá para trocar depois, dentro do app).
2. Abra a pasta `android` no Android Studio e espere a sincronização.
3. Use **Build > Generate App Bundles or APKs > Generate APKs**.
4. O arquivo `app-debug.apk` fica em `android/app/build/outputs/apk/debug/`. Instale no celular permitindo fontes desconhecidas.

O app só conecta quando o servidor está ligado e o celular está na mesma rede.

## Segurança

Este servidor dá controle sobre o PC. Por isso:

- Toda ação exige o **token** (cabeçalho `X-Token`).
- O servidor só aceita conexões de **rede local** (e do Tailscale).
- 5 tokens errados bloqueiam o aparelho por 1 minuto.
- As ações usam `POST`, e teclas e atalhos vêm de listas fechadas no servidor.
- O `token.txt` está no `.gitignore`.

**Limites:** a comunicação usa HTTP sem criptografia, então use apenas em redes que você controla. Quem tiver o token e estiver na sua rede controla o PC. **Nunca abra a porta 5000 no roteador.** Para usar fora de casa, use uma VPN como o Tailscale.

## Estrutura

```
controle-pc-celular/
  README.md
  servidor/     servidor Flask, interface e scripts do Windows
  android/      projeto do Android Studio (app WebView)
  docs/         guia de aula em PDF
```

## Limitações

- Funciona somente no Windows.
- A captura de tela pega só o monitor principal.
- O controle de LEDs não está incluído.
- O IP do PC pode mudar. Fixar o IP no roteador evita isso.
- Usa o servidor de desenvolvimento do Flask, suficiente para uso pessoal em casa.
