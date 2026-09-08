# Repor a integração MCP deste PC

Este repositório guarda os componentes locais dos três MCPs: Bridge, Unity e
Blender. O inventário em `ops/config/installation.json` regista versões, caminhos
e hashes dos binários existentes na data da cópia. O código do Bridge está na raiz.

O destino original é `/home/user/chatgpt-local-bridge`, apesar de o repositório
GitHub se chamar `pc-mcp-integration`. Os launchers, serviços e aliases usam caminhos
absolutos. Noutro utilizador ou projeto, adaptar esses caminhos antes de instalar.

## O que está guardado

| Origem no repositório | Destino / finalidade |
| --- | --- |
| `bridge.py`, `mcp_server.py`, `security.py`, `applications.py`, `bridge_config.json` | Servidor Local Dev Bridge e política atual de acesso ao PC |
| `requirements.lock` | Dependências exatas do Bridge; Python 3.14.4 |
| `ops/{launch,supervise,blender_entry,mcp-services}.py` | `/home/user/.local/lib/mcp-integration/` |
| `ops/bin/mcp-services` | `/home/user/.local/bin/mcp-services` |
| `ops/units/*.service` | `/home/user/.config/systemd/user/` |
| `ops/config/tunnel-client/*.yaml` | `/home/user/.config/tunnel-client/` |
| `ops/config/global-agent-instructions.md` | Conteúdo de `/home/user/AGENTS.md` |
| `ops/config/unity/AI-Game-Developer-Config.example.json` | Preferências MCP de `ExampleGame/UserSettings/`; token removido |
| `ops/config/unity/packages-mcp.json` | Fragmentos das dependências MCP e registry do Unity; não substituir o manifest completo |
| `ops/vendor/blender-mcp/blender_mcp.py` | Complemento instalado no Blender, versão 1.6 / protocolo 5, com licença MIT |
| `ops/blender-requirements.lock`, `ops/blender_entry.py` | Servidor Blender MCP 1.9.1 e adaptações locais |
| `ops/config/codex-blender.toml` | Entrada local Blender opcional; integrar no config existente sem o substituir |

Os perfis preservam os IDs dos três túneis existentes e as portas locais
8080 (Bridge), 8081 (Unity) e 8082 (Blender). Cada `api_key` aponta para um ficheiro;
nenhum contém a chave. Os IDs não substituem a autenticação.

## Elementos que têm de existir separadamente

- As três chaves em `/home/user/.config/mcp-integration/credentials/`:
  `chatgpt-local-bridge.key`, `chatgpt-unity.key` e `chatgpt-blender.key`.
  Recuperá-las de uma cópia privada ou obter credenciais válidas pela configuração
  da conta original. Sem estas chaves, o clone sozinho não restabelece a ligação.
- A conta original do ChatGPT e as suas três ligações MCP. A autorização e o
  catálogo guardados na conta não são exportados pelo Git. A conta Codex é independente.
- O executável `tunnel-client` em `/home/user/.local/bin/tunnel-client`.
  Versão capturada: `0.0.14+0f870e50a973fa820d4c409000059e181e8d242b`.
  Repor a distribuição oficial ou uma cópia privada compatível; o hash está no inventário.
- `uv`, Python, Bubblewrap, Git, `rg` e systemd com gestor de serviços de utilizador.
  Os hashes e versões de referência estão no inventário; dependências Python estão nos locks.
- Unity Editor `6000.6.0f1` e o projeto `/home/user/Projects/ExampleGame`, recuperado
  do seu próprio repositório/backup. Blender `5.2.1 LTS` instalado via Snap.
  Os jogos, cenas, assets, preferências completas dos Editors e binários não estão aqui.

## Recuperação numa instalação nova com os mesmos caminhos

Este procedimento destina-se a uma recuperação. Não é necessário executá-lo no PC
atual, onde os serviços já estão instalados. Se existirem configurações mais recentes,
comparar e integrar as diferenças antes de copiar ficheiros sobre elas.

### 1. Código e ambientes Python

```sh
git clone git@github.com:SomeGuySomewhereSometime/pc-mcp-integration.git /home/user/chatgpt-local-bridge
cd /home/user/chatgpt-local-bridge
uv venv --python 3.14.4 .venv
uv pip sync --python .venv/bin/python requirements.lock
uv tool install --python 3.12.13 --link-mode copy --with-requirements ops/blender-requirements.lock blender-mcp==1.9.1
```

Os downloads continuam a depender da disponibilidade dos distribuidores. Os locks
registam versões, não constituem um arquivo offline de todos os pacotes.

### 2. Launchers, perfis e serviços

Executar a partir da raiz do clone:

```sh
install -d -m 755 /home/user/.local/lib/mcp-integration /home/user/.local/bin
install -m 644 ops/launch.py ops/supervise.py ops/blender_entry.py ops/mcp-services.py /home/user/.local/lib/mcp-integration/
install -m 755 ops/bin/mcp-services /home/user/.local/bin/mcp-services
install -d -m 700 /home/user/.config/mcp-integration/credentials /home/user/.config/tunnel-client
install -m 600 ops/config/tunnel-client/*.yaml /home/user/.config/tunnel-client/
install -d -m 755 /home/user/.config/systemd/user
install -m 644 ops/units/*.service /home/user/.config/systemd/user/
```

Repor as três chaves nos caminhos indicados, com permissões `0600` e diretório de
credenciais `0700`. Não colocar os valores em comandos, logs ou commits. Repor
`ops/config/global-agent-instructions.md` como `/home/user/AGENTS.md`, ou integrar
as regras numa versão existente. O Bridge e o wrapper Blender leem esse ficheiro.

Para a ligação Blender local opcional do Codex, integrar apenas a secção de
`ops/config/codex-blender.toml` em `~/.codex/config.toml`. Não copiar contas, tokens
ou o ficheiro de configuração inteiro de outro utilizador.

### 3. Unity

Restaurar o projeto e verificar as dependências de `ops/config/unity/packages-mcp.json`
no seu manifest. O plugin principal é `com.ivanmurzak.unity.mcp` 0.90.0; o servidor
gerido por esse plugin era 9.2.5. As extensões têm versões próprias, registadas no snapshot.

Comparar o exemplo de preferências com
`/home/user/Projects/ExampleGame/UserSettings/AI-Game-Developer-Config.json` e repor
as opções necessárias. O exemplo preserva 145 entradas de ferramentas, 114 ativas,
e as opções de prompts/recursos. O token está vazio porque a configuração local
capturada usa `authOption: none`; o valor original foi deliberadamente omitido.
Guardar o ficheiro com permissões `0600`.

Abrir o projeto no Editor e confirmar a ligação em **Window → AI Game Developer — MCP**.
O endpoint do perfil atual é `http://127.0.0.1:22153/p/4964095b`; esse identificador
é derivado do caminho do projeto e muda se o projeto mudar de pasta.

Confirmar as cinco ferramentas que foram ativadas:
`editor-application-get-state`, `editor-application-set-state`,
`screenshot-game-view`, `screenshot-scene-view` e `screenshot-camera`.

### 4. Blender

Instalar/ativar a cópia `ops/vendor/blender-mcp/blender_mcp.py` através das preferências
de complementos do Blender. O destino original era
`/home/user/.config/blender/5.2/scripts/addons/blender_mcp.py`.
O ficheiro é uma cópia sem alterações do addon instalado, com protocolo 5.

Abrir o painel **MCP for Blender** e iniciar a ligação local na porta 9876.
Desativar o consentimento de telemetria do addon e guardar as preferências.
O launcher já desativa a telemetria do servidor; as capacidades de autoria Python
continuam disponíveis. Preferências binárias, chaves opcionais de serviços de assets
e ficheiros `.blend` não foram copiados.

### 5. Arranque e verificação

Depois de repor os executáveis, chaves e configurações:

```sh
systemctl --user daemon-reload
systemctl --user enable --now mcp-tunnel-chatgpt-local-bridge.service mcp-tunnel-chatgpt-unity.service mcp-tunnel-chatgpt-blender.service
/home/user/.local/bin/mcp-services status
```

Os serviços arrancam no login do utilizador. O PC precisa de sessão iniciada,
Internet e de permanecer acordado. Unity e Blender têm de estar abertos e ligados
aos respetivos MCPs para executar operações nos Editors.

Na conta original do ChatGPT, confirmar as três ligações existentes e atualizar o
catálogo se necessário. Abrir uma conversa com os MCPs disponíveis e fazer uma
chamada de leitura em cada um. Esperado nesta instalação: Bridge 20 ferramentas,
Blender 30 e Unity 114. IDs/credenciais antigos só funcionam enquanto a autorização
correspondente continuar válida na conta; recriar uma ligação exige atualizar o perfil.

Para validar o Bridge fora da sandbox de outro agente:

```sh
BRIDGE_SANDBOX_TESTS=1 BRIDGE_SYSTEMD_TESTS=1 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest -v
```

A versão guardada passou 29 testes e recuperação de uma falha controlada do Bridge.
Não foi realizada uma recuperação completa numa máquina limpa nem um reboot real.
Este procedimento foi revisto contra os caminhos e ficheiros instalados; não foi
executado sobre a instalação em funcionamento para produzir este backup.
