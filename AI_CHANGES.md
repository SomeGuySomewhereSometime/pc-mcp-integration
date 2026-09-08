# AI Changes

## 2026-09-07 19:40 WEST — ChatGPT

### Tarefa
Evoluir o Local Dev Bridge de coding bridge para development/computer bridge.

### Ficheiros alterados
- `bridge.py`
- `mcp_server.py`
- `test_bridge.py`
- `AI_CHANGES.md`

### Alterações
Adicionadas as ferramentas system_info, process_list, process_kill, screen_capture, app_launch, app_close, mkdir, move e delete, mantendo intactas as ferramentas de coding existentes e o run_command com Bubblewrap. screen_capture usa gnome-screenshot quando disponível, xdg-desktop-portal como backend principal compatível com GNOME/Wayland, e org.gnome.Shell.Screenshot como fallback. app_launch usa argv direto com shell=False e bloqueia shells/intérpretes óbvios para não criar um bypass ao run_command. process_kill limita sinais e protege PID 1/bridge/outro utilizador. mkdir/move/delete continuam confinados a BRIDGE_WORKSPACE e delete exige recursive=true para árvores.

### Motivo
Transformar o MCP numa bridge de desenvolvimento/computador com operações dedicadas em vez de alargar o shell genérico, aproveitando padrões úteis do alexcodeplace/chatgpt-mcp.

### Testes
- python3 -m py_compile bridge.py mcp_server.py
- ./.venv/bin/python -m py_compile bridge.py mcp_server.py
- BRIDGE_WORKSPACE=/home/user ./.venv/bin/python -m unittest -v test_bridge.py — 8 testes OK
- BRIDGE_WORKSPACE=/home/user ./.venv/bin/python -c 'import mcp_server' — OK
- Teste real de screen_capture: portal criou request mas ficou à espera de consentimento e expirou; fallback org.gnome.Shell.Screenshot devolveu AccessDenied no contexto sandboxed
- Teste de run_command dentro do próprio run_command não conseguiu criar um segundo namespace Bubblewrap; isto é uma limitação de nested-bwrap do ambiente de teste, não uma alteração ao código de run_command

### Estado
Implementado e testado; requer reinício do MCP para expor as novas ferramentas.

### Observações
O diretório /home/user/chatgpt-local-bridge não é um repositório Git. O diff foi revisto com git diff --no-index contra snapshots dos dois ficheiros originais. Não foi implementado controlo de rato/teclado.

## 2026-09-07 20:01 WEST — ChatGPT

### Tarefa
Implementar com segurança system_info, process_list, process_kill, screen_capture, app_launch e app_close, mantendo as ferramentas existentes e o Bubblewrap.

### Ficheiros alterados
- `bridge.py`
- `mcp_server.py`
- `test_bridge.py`
- `bridge_config.json`
- `AI_CHANGES.md`

### Alterações
Endurecida a implementação das capacidades de host: process_kill passou a ser deny-by-default e exige executável/sinal permitidos em bridge_config.json; app_launch aceita apenas aliases explicitamente configurados, usa argv direto com shell=False e argumentos desativados por defeito; app_close usa um handle opaco emitido por app_launch em vez de aceitar PIDs arbitrários; process_list omite argumentos completos por defeito e só os mostra com include_args=true; screen_capture usa xdg-desktop-portal como backend principal para Ubuntu GNOME/Wayland, com GNOME Shell D-Bus e gnome-screenshot como fallbacks, guarda apenas PNG dentro do workspace e o MCP devolve também ImageContent. system_info inclui o caminho da configuração. run_command/Bubblewrap e as restantes tools não foram alargados ou removidos.

### Motivo
Seguir o padrão arquitetural de capacidades dedicadas e política explícita observado no alexcodeplace/chatgpt-mcp, evitando transformar run_command num bypass de controlo do host.

### Testes
- ./.venv/bin/python -m py_compile bridge.py mcp_server.py test_bridge.py — OK
- BRIDGE_WORKSPACE=/home/user ./.venv/bin/python -m unittest -v test_bridge.py — 15 testes OK
- BRIDGE_WORKSPACE=/home/user ./.venv/bin/python -c 'import mcp_server' — OK
- Smoke test GNOME Shell Screenshot via D-Bus no contexto sandboxed devolveu AccessDenied; por isso xdg-desktop-portal ficou como backend principal

### Estado
Implementado diretamente em /home/user/chatgpt-local-bridge e testado; o MCP em execução ainda não foi reiniciado para recarregar os novos schemas.

### Observações
Não foi implementado controlo de rato/teclado. /home/user/chatgpt-local-bridge não contém .git, por isso o diff final foi revisto com git diff --no-index contra snapshots locais criados antes desta tarefa.

## 2026-09-07 20:11 WEST — ChatGPT

### Tarefa
Corrigir regressão de segurança no workspace efetivo do Local Dev Bridge.

### Ficheiros alterados
- `~/.config/tunnel-client/chatgpt-local-bridge.yaml`
- `AI_CHANGES.md`

### Alterações
O teste pós-reinício revelou que o MCP estava a herdar BRIDGE_WORKSPACE=/home/user da shell, alargando involuntariamente o workspace para toda a home. O perfil ~/.config/tunnel-client/chatgpt-local-bridge.yaml foi alterado para arrancar o MCP via /usr/bin/env com BRIDGE_WORKSPACE=/home/user/Projects explicitamente fixado, preservando a fronteira original em futuros arranques.

### Motivo
O requisito original era manter o workspace e as restrições atuais. Fixar a variável no perfil impede que um valor mais amplo herdado da shell enfraqueça essa fronteira.

### Testes
- Leitura do perfil atual confirmou que não fixava BRIDGE_WORKSPACE.
- system_info da sessão nova revelou workspace=/home/user, identificando a regressão.

### Estado
Configuração corrigida; requer reinício do tunnel-client para entrar em vigor.

### Observações
Não foi alterado o Bubblewrap nem o run_command. Não foi implementado controlo de rato/teclado.

## 2026-09-07 20:15 WEST — ChatGPT

### Tarefa
Alargar explicitamente o workspace do Local Dev Bridge e do run_command para /home/user, por preferência do utilizador, mantendo Bubblewrap.

### Ficheiros alterados
- `bridge.py`
- `test_bridge.py`
- `~/.config/tunnel-client/chatgpt-local-bridge.yaml`
- `AI_CHANGES.md`

### Alterações
BRIDGE_WORKSPACE fica fixado em /home/user no perfil do tunnel-client. COMMAND_WORKSPACE passa a seguir WORKSPACE, por isso run_command pode operar em qualquer caminho dentro de /home/user. O Bubblewrap, a rede desativada e os padrões de comandos destrutivos continuam ativos. safe_command_path continua a bloquear cwd fora de /home/user.

### Motivo
O utilizador esclareceu que prefere que o próprio run_command também possa aceder a toda a sua home /home/user.

### Testes
- ./.venv/bin/python -m py_compile bridge.py mcp_server.py test_bridge.py — OK
- BRIDGE_WORKSPACE=/home/user ./.venv/bin/python -m unittest -v test_bridge.py — 16 testes OK
- Fresh import confirmou WORKSPACE=/home/user e COMMAND_WORKSPACE=/home/user

### Estado
Implementado e testado; requer reinício do tunnel-client para o perfil atualizado entrar em vigor.

### Observações
Bubblewrap não foi removido; run_command continua sem rede e com bloqueios de comandos destrutivos. Não foi implementado controlo de rato/teclado.

## 2026-09-08 00:10 WEST — Codex

### Tarefa
Implementar as correções e melhorias autorizadas após a auditoria dos três MCPs, mantendo as capacidades úteis de desenvolvimento e autoria Python/C#.

### Ficheiros alterados
- Bridge: `bridge.py`, `security.py`, `mcp_server.py`, `bridge_config.json`, `test_bridge.py`, `test_security.py`, `requirements.lock`, `README.md`, `.gitignore` e este registo.
- Operação reproduzível: `ops/launch.py`, `ops/blender_entry.py`, `ops/supervise.py`, `ops/mcp-services.py`, `ops/units/` e `ops/blender-requirements.lock`; cópias instaladas em `~/.local/lib/mcp-integration/` e CLI `~/.local/bin/mcp-services`.
- `/home/user/AGENTS.md`, três perfis `~/.config/tunnel-client/chatgpt-*.yaml`, três units em `~/.config/systemd/user/`, configuração MCP Blender em `~/.codex/config.toml` e diretórios privados de credenciais/backup.
- Unity `UserSettings/AI-Game-Developer-Config.json`: apenas permissões 0600; ferramentas escolhidas pelo utilizador preservadas. Blender: consentimento de telemetria desativado pela API nativa; preferência guardada automaticamente, addon sem alterações.

### Alterações e motivo
- Corrigidas operações move/delete sobre raiz, caminhos sobrepostos e symlinks; overwrite nunca elimina recursivamente o destino. Pesquisa deixou de seguir links externos.
- Aplicada a política de caminhos às ferramentas de ficheiros e sandbox Bubblewrap de shell, Git, pesquisa e patches; sockets de host em /run isolados, credenciais protegidas e ficheiros de controlo só de leitura. Mantido o workspace /home/user autorizado anteriormente e a rede de shell já desativada.
- Removida herança indiscriminada do ambiente: as chaves dos túneis ficam referenciadas por ficheiros privados 0600 e não seguem para processos MCP.
- Corrigidos launchers para Blender Snap 5.2.1 e Unity Editor/ExampleGame; instâncias abertas são reutilizadas.
- Acrescentados get_session_context e integration_status ao Bridge e get_context/get_scene_objects ao wrapper Blender. Instruções globais incluídas na inicialização dos dois servidores.
- Blender MCP fixado em 1.9.1 num uv tool install persistente, com dependências atuais congeladas e ficheiros copiados; addon 1.6/protocolo 5 preservado. Telemetria detalhada e anónima desativada no arranque; não foi ativado safe mode nem retirada execução Python/C#.
- Três serviços systemd --user ativos e habilitados para login; logs no journal, CLI start/stop/restart/status e supervisão da morte de filhos stdio. Túneis, endpoints e portas originais preservados. O perfil codex-chatgpt-web permanece independente.
- Reforçadas regras globais de identidade, inventário efetivo, concorrência de mutações, recuperação sem duplicação e validação de transferências Blender/Unity. Git inicializado no Bridge para futuras revisões, sem staging, commit, remote ou push.

### Testes e verificações
- 26 testes unittest passaram, incluindo testes reais Bubblewrap de IPC, caminhos protegidos, symlinks, pesquisa e patches com dados sintéticos descartáveis.
- Inicialização MCP nova: Bridge 20 tools, Blender 30; contexto/regras globais, paginação e nova ferramenta integration_status validados.
- Três serviços ativos, health/ready HTTP 200 e processos MCP presentes. Falha controlada do filho MCP Bridge recuperada automaticamente em cerca de 7.4 segundos; Editors mantidos abertos.
- Unity: 114 ferramentas, cinco ferramentas de estado/screenshots habilitadas, scene VeilboundShrine sem alterações pendentes, sem compilação/Play Mode e sem erros recentes na Console; captura nativa da Game View obtida e inspecionada.
- Blender: 5.2.1 LTS, addon atualizado/protocolo 5, contexto Cube/OBJECT, paginação válida, consentimento false e preferências sem alterações por guardar.
- Após a mudança de conta, chamadas reais através dos três plugins tiveram sucesso: Local Dev Bridge system_info, Blender get_addon_status, Unity scene_list_opened e console_get_logs.
- Chaves não impressas, addon não bifurcado, versões existentes preservadas. Backup privado dos originais em `/home/user/.local/state/mcp-integration/backups/20260907-235634`.

### Resultado e limites
Implementação instalada e em execução. O catálogo dos conectores ChatGPT ainda precisa de Refresh nas três ligações existentes para incluir novas ferramentas e ferramentas Unity recém-ativadas; o navegador de automação não tem sessão ChatGPT iniciada. Não é necessário recriar túneis ou chaves. Não foi feito reboot/login completo nem teste de gameplay em Play Mode; esta tarefa altera a integração, não o jogo. A política de caminhos não é contenção contra um processo hostil do mesmo utilizador e não classifica automaticamente segredos de todos os projetos.

## 2026-09-08 02:26 WEST — Codex — verificação final

### Tarefa e alterações
Concluir a integração após o Refresh dos três MCPs efetuado pelo utilizador, mantendo a conta original dos túneis separada da conta atual do Codex. Corrigidos os metadados de nove ferramentas exclusivamente de leitura do Bridge em `mcp_server.py` e dos dois helpers de contexto Blender no wrapper instalado e `ops/blender_entry.py`: readOnly=true, destructive=false, openWorld=false. Nenhuma permissão ou capacidade de autoria foi alterada. Atualizado README.

### Verificação
- Suite instalada: 26 testes passaram, incluindo Bubblewrap real.
- Sessões MCP novas confirmaram 20 tools Bridge e 30 Blender, regras globais, metadados de leitura e chamadas reais `integration_status`/`get_context` bem-sucedidas.
- Os servidores Bridge e Blender foram recarregados; os três serviços continuam active/enabled, health/ready HTTP 200. As instâncias Unity e Blender originais continuam abertas.
- Após o login feito pelo utilizador na conta original no navegador, confirmado o catálogo do ChatGPT: `get_session_context`/`integration_status` e `get_context`/`get_scene_objects` presentes e classificados LER. O Refresh final destes dois catálogos foi concluído na interface.
- No catálogo Unity atualizado estão `editor-application-get-state`, `editor-application-set-state`, `screenshot-game-view`, `screenshot-scene-view` e `screenshot-camera`.
- Mantidos os três túneis/credenciais e as permissões de confirmação existentes; nenhuma associação à outra conta Codex foi criada.

### Resultado
Correções instaladas, testes concluídos e catálogo atualizado. A pendência de login/Refresh da entrada anterior está resolvida. Não é necessária alteração de API, conta, addon ou túnel pelo utilizador. Um chat que conserve ferramentas antigas deve iniciar uma nova conversa com as três ligações existentes. Não foi testado um reboot completo nem gameplay em Play Mode. Sem commit/push.

## 2026-09-08 02:54 WEST — Codex — Bridge 0.4.1

### Tarefa
Corrigir os três problemas da segunda auditoria, validar a recuperação e preparar o primeiro commit local, conforme autorização do utilizador.

### Ficheiros e alterações
- `applications.py` (novo) e `bridge.py`: aplicações iniciadas em units systemd de utilizador independentes `mcp-app-*.service`, com ambiente permitido explícito e argumentos literais. O gestor de serviços é o pai; o processo não pertence ao grupo do túnel. Sem fallback Popen que reintroduza o problema. `app_close` continua limitado a handles emitidos pela instância atual e envia TERM ou KILL apenas quando force=true.
- `security.py`: identidade global Git reduzida a user.name/user.email num ficheiro efémero só de leitura dentro da sandbox; configuração local do repositório mantém precedência. Helpers, hooks e restantes opções globais não são transportados.
- `bridge.py`/`security.py`: arranque recusa configuração ausente, inválida ou sem as duas listas obrigatórias de caminhos. Versão 0.4.1.
- `test_regressions.py` (novo), `test_bridge.py`, `test_security.py`: cobertura dos três defeitos e adaptação dos testes de launcher.
- `README.md`: documentado ciclo de vida independente, identidade Git e arranque estrito.

### Validação
- 29 testes passaram tanto na preparação como na instalação, com BRIDGE_SANDBOX_TESTS=1 e BRIDGE_SYSTEMD_TESTS=1.
- Serviço descartável executou o app_launch real: aplicação de teste sobreviveu ao stop do lançador com KillMode=control-group; cgroups distintos, argumentos $/% preservados e chave sintética não herdada. Todos os serviços de teste foram terminados no cleanup.
- Commit real em repositório descartável dentro da sandbox: identidade global disponível, identidade local com precedência e helpers/hooks/assinatura globais ausentes.
- Nova inicialização sem bridge_config.json recusada antes de servir ferramentas.
- Chamada MCP real no ExampleGame: git var GIT_AUTHOR_IDENT passou sem revelar identidade; launcher reutilizou o Unity existente (PID 389947). Catálogo permanece com 20 ferramentas.
- Após instalação e restart do Bridge, falha TERM simulada apenas no seu filho MCP: recuperação automática em 5.78 segundos. Unity e Blender originais permaneceram abertos.
- Backup dos originais: `/home/user/.local/state/mcp-integration/backups/20260908-014558-lifecycle`.

### Resultado e limites
Correções ativas, sem alterações de cenas, contas, credenciais, túneis ou addons. A independência de aplicações foi comprovada com processo descartável e os mesmos caminhos de lançamento/systemd, sem fechar/reabrir os Editors. O arranque foi validado em serviços com ambiente limpo; não foi feito logout/login ou reboot real. Supervisão continua orientada à saída de processos; não foi acrescentado reinício automático por simples lentidão/hang. Handles app_close permanecem locais à sessão, como anteriormente. Preparado o primeiro commit local do Bridge, sem remote ou push.
