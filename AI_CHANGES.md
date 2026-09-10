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

## 2026-09-08 — Backup dos três MCPs para GitHub privado

### Tarefa
Guardar a integração usada para aceder ao PC, conforme pedido do utilizador, num
novo repositório privado `SomeGuySomewhereSometime/pc-mcp-integration`.

### Alterações
- README passou a apresentar o conjunto Bridge/Unity/Blender; RESTORE.md documenta
  o mapa de instalação, dependências, recuperação e elementos externos necessários.
- `ops/config/` guarda os três perfis com referências a ficheiros de chaves,
  instruções globais, inventário de versões/hashes, entrada Blender local opcional
  e configurações/pacotes MCP Unity. Token Unity omitido; 114 ferramentas ativas preservadas.
- `ops/bin/mcp-services` guarda o comando instalado. `ops/vendor/blender-mcp/`
  guarda a cópia exata do addon 1.6/protocolo 5 e a licença MIT original.
- `.gitignore` exclui ficheiros usuais de credenciais, ambientes e backups.

### Verificação
- Cópias dos quatro scripts operacionais e três serviços correspondem à instalação;
  addon e instruções globais também foram comparados byte a byte.
- O blob Git do addon instalado corresponde ao upstream verificado no momento da cópia.
- Validação sintática de Python, JSON, YAML, TOML e launcher shell passou. Confirmados
  os três campos api_key como referências file:, token Unity vazio e cinco ferramentas
  de estado/screenshots ativas. Pesquisa de padrões de credenciais sem ocorrências.
- Os 29 testes do Bridge tinham passado antes deste empacotamento; o código de
  execução do Bridge e os scripts operacionais não foram alterados nesta tarefa.

### Limites
Não inclui chaves, sessões/login, autorização da conta ChatGPT, binários ou projetos
Unity/Blender. Os locks dependem dos distribuidores dos pacotes; não são um arquivo
offline. Não foi executada uma recuperação numa máquina limpa. A instalação em
funcionamento e as contas dos túneis não foram alteradas por este backup.
# 2026-09-08 — Desktop observation and control in the installed Bridge

- Request: preserve the current version locally and on GitHub, then implement desktop
  control in the installed Bridge, leaving installers unchanged.
- Backup: verified local archive and Git bundle in
  `/home/user/chatgpt-local-bridge-backups/pre-desktop-20260908T220345Z`; annotated
  GitHub tag `backup/pre-desktop-20260908T220345Z` resolves to `92c4151f308dd0b768475a45b4de3e2b0660359c`.
- Changes: desktop.py (bounded private helper client), desktop_worker.py (AT-SPI and
  GNOME RemoteDesktop/PipeWire), four MCP tools in mcp_server.py, version 0.5.0,
  desktop.enabled configuration, protocol/MCP/live tests, disposable GTK fixture,
  manual-consent portal acceptance, and README integration/recovery instructions.
- Behavior: snapshots bound to observations, revalidated element targets, short
  explicit action batches, partial failure receipts, Unicode editable-text readback,
  monitor-relative visual input, native MCP PNG results, bounded parent-owned session
  and explicit GNOME consent. No new tunnel, installer, API model or runtime dependency.
- Validation before deployment: all 29 existing tests passed with real Bubblewrap
  and systemd checks; 10 desktop protocol tests and 4 MCP output/configuration tests
  passed. Real GTK fixture passed text readback, button result, checkbox and stale ID
  refusal. Portal fixture passed live monitor image, real key, Unicode insertion,
  click, slider drag (0 to 85), and refusal after session closure. PNG inspected.
- Limitations: final ChatGPT catalog refresh and use of the new tools by Sol remain
  to be verified in the user's conversation. Single selected monitor per session;
  app-specific AT-SPI coverage varies. Raw non-ASCII key events are refused; Unicode
  text uses an observed editable field. Existing filesystem sandbox remains intact,
  but it is not a containment boundary for user-authorized desktop control.

- Deployment verification: installed in /home/user/chatgpt-local-bridge; restarted only
  mcp-tunnel-chatgpt-local-bridge.service. healthz and readyz returned HTTP 200.
  A fresh MCP wire session from the installed code listed 24 tools and passed
  Unicode text readback plus a model-readable stale-snapshot error.
- Follow-up diagnostics: Firefox is running but no application named Firefox is
  registered in the current AT-SPI inventory. This is accessibility coverage, not
  a Firefox prohibition in the Bridge. No Firefox preferences were changed.
- Remaining acceptance: the initial portal test passed keyboard, Unicode insertion,
  click, drag and session closure. A subsequent startup intermittently received no
  frame. The final code adds bounded event-loop pumping and disables sink preroll;
  its live repeat and the added scroll assertion await local GNOME consent (last
  permission request timed out). Do not call that final repeat passed. ChatGPT
  Refresh and a real Sol action using the new catalog are also pending.

## 2026-09-09 01:51 WEST — ChatGPT

### Tarefa
Relax Local Dev Bridge restrictions that were blocking legitimate diagnostics and normal development work while preserving destructive filesystem boundaries.

### Ficheiros alterados
- `security.py`
- `bridge.py`
- `mcp_server.py`
- `bridge_config.json`
- `test_bridge.py`
- `test_security.py`
- `check_desktop_mcp.py`
- `README.md`
- `AI_CHANGES.md`

### Alterações
Added opt-in Bubblewrap host networking and enabled it in the operator config; added bounded host process diagnostics with AppArmor/cgroup/namespace information; added bounded journal/kernel querying; exposed both as read-only MCP tools; bumped Bridge to 0.6.0 and updated catalog/test expectations and documentation.

### Motivo
The command sandbox's isolated network and /proc view were preventing legitimate development and diagnosis, including identifying AppArmor/Snap interactions with Firefox. Dedicated host diagnostics solve the /proc problem without exposing the host PID namespace to arbitrary shell commands, while configurable networking restores common development workflows.

### Testes
- 29 targeted Bridge/security tests: OK, 4 expected integration skips
- 38-test normal unittest suite: OK, 8 expected integration skips
- MCP wire catalog probe: 26 tools; process_info, journal_query and all desktop tools present
- Real journal_query(kernel_only=true, query=apparmor): returned bounded AppArmor kernel events
- Host Bubblewrap integration suite attempted from inside the active Bridge sandbox; nested user namespaces were refused by the environment, so those host-only tests must be rerun outside an existing Bridge command sandbox

### Estado
Staged in a second working copy of the same pc-mcp-integration repository; active Bridge has not been overwritten.

### Observações
Pre-change commit d4d9679 is tagged backup/pre-relaxed-security-20260909T004258Z. Network retains Bubblewrap mount/PID/IPC/user isolation, capability dropping, private HOME/runtime mounts and protected paths; only the network namespace is shared when sandbox.network=true.

## 2026-09-09 01:56 WEST — ChatGPT

### Tarefa
Fix DNS inside the relaxed Bubblewrap network mode

### Ficheiros alterados
- `security.py`

### Alterações
When sandbox.network is enabled, re-expose only /run/systemd/resolve read-only so Ubuntu's /etc/resolv.conf symlink continues to resolve DNS while the rest of /run remains isolated.

### Motivo
The first 0.6.0 deployment correctly retained the host network namespace but DNS lookups failed because /etc/resolv.conf points into the otherwise private /run mount.

### Testes
- Targeted sandbox network policy unit test passed
- Full Python suite: 38 tests passed, 8 expected integration skips

### Estado
Staged fix ready for deployment as 0.6.1.

### Observações
Real DNS resolution must be verified after copying the fix into the active Bridge and restarting it.

## 2026-09-09 02:05 WEST — ChatGPT

### Tarefa
Reduce unnecessary desktop-control friction for Firefox and modern web apps

### Ficheiros alterados
- `desktop_worker.py`
- `test_desktop.py`
- `bridge.py`
- `README.md`

### Alterações
Verified Firefox exposes a rich AT-SPI tree and changed the Bridge rather than Firefox: desktop observation now traverses through up to two non-showing intermediary wrappers while still emitting only showing/useful nodes, and type_text can use a unique focused AT-SPI EditableText field without requiring a GNOME RemoteDesktop session or screenshot. Raw input still requires the authorized portal path. Bumped Bridge version to 0.6.2 and documented the behavior.

### Motivo
The remaining failures were Bridge traversal/input-policy friction, not an AppArmor denial or fundamental Firefox limitation.

### Testes
- /usr/bin/python3 -B -m unittest -v test_desktop: 11/11 passed
- Active Bridge venv: test_bridge test_security test_desktop_mcp: 29 passed, 4 expected integration skips
- git diff --check: clean

### Estado
Ready for deployment to the active Bridge; no MCP tool/schema change, so no catalog refresh required.

### Observações
Live verification of the modified worker requires deployment/restart because the active Bridge marks its own installation read-only.

## 2026-09-09 02:13 WEST — ChatGPT

### Tarefa
Add semantic-focus keyboard fallback for rich Firefox web editors

### Ficheiros alterados
- `desktop_worker.py`
- `test_desktop.py`
- `mcp_server.py`
- `bridge.py`
- `README.md`

### Alterações
`type_text` now inspects the unique focused AT-SPI editor before mutation. Reliable caret/selection state keeps verified AT-SPI insertion. An unreliable caret, as exposed by the ChatGPT rich composer in Firefox, triggers an authorized GNOME RemoteDesktop keyboard fallback using the already-established semantic focus, with no screenshot or pointer coordinates. Added Unicode X11 keysyms for printable non-ASCII characters. Pointer input retains the existing screenshot requirement. Version bumped to 0.6.3.

### Motivo
Live v0.6.2 testing proved semantic navigation and composer discovery work, but Firefox reports an invalid caret for the ChatGPT contenteditable editor and `set_text_contents` is a no-op despite returning success.

### Testes
- `/usr/bin/python3 -B -m unittest -v test_desktop`: 12/12 passed
- Active Bridge venv targeted suite: 29 passed, 4 expected integration skips
- Full discovery: 38 tests passed with 8 expected integration skips
- `git diff --check`: clean

### Estado
Ready for deployment as v0.6.3. No MCP tool names or schemas changed.

## 2026-09-09 02:29 WEST — ChatGPT

### Tarefa
Fix GNOME RemoteDesktop consent dialog staying pending without a visible window.

### Ficheiros alterados
- `desktop_worker.py`
- `test_desktop.py`
- `bridge.py`
- `README.md`

### Alterações
The worker no longer calls `RemoteDesktop.Start` with an empty parent on Wayland. It creates a transparent 1x1 GTK4 parent, exports an xdg-foreign handle with GdkWayland, passes `wayland:<handle>` to the portal, and releases the exported handle/window on close. Added a regression test that drives the portal callback chain and asserts Start receives a non-empty Wayland parent. Version bumped to 0.6.4.

### Motivo
The host journal showed `xdg-desktop-portal-gnome: Failed to associate portal window with parent window` at the exact consent attempt, and no dialog appeared. The XDG portal API defines `parent_window` as the application window identifier; GNOME/Wayland in this environment did not reliably present the dialog with an empty identifier.

### Testes
- `/usr/bin/python3 -B -m unittest -v test_desktop`: 13/13 passed
- active Bridge venv: `test_bridge test_security test_desktop_mcp`: 29 passed, 4 expected host-integration skips
- `python3 -m py_compile desktop_worker.py`: passed

### Estado
Ready for deployment as v0.6.4. No MCP tool/schema change; plugin refresh is not required.

## 2026-09-09 — ChatGPT — v0.6.5 rich-editor semantic descendant input

### Tarefa
Improve Unicode typing in Firefox rich web editors without clipboard or pointer coordinates.

### Alterações
- When the uniquely focused AT-SPI editor wrapper has an invalid caret, search only its bounded descendant tree for exactly one visible editable Text/EditableText node with sane caret/selection state.
- Use that descendant for verified semantic insertion; ambiguous or unavailable descendants retain the authorized portal-keyboard fallback.
- Pass Unicode insertion length to AT-SPI as character count rather than UTF-8 byte count.
- Added tests for descendant selection and multi-byte Unicode character length.
- Version bumped to 0.6.5.

### Testes
- `/usr/bin/python3 -B -m unittest -v test_desktop`: 15/15 passed.
- Active Bridge venv: `test_bridge test_security test_desktop_mcp`: 29 passed, 4 expected integration skips.
- `git diff --check`: clean.

### Estado
Ready for deployment and live Firefox/ChatGPT composer verification. No MCP tool names or schemas changed.

## 2026-09-09 — ChatGPT — v0.6.6 empty rich-editor Unicode insertion

### Tarefa
Handle the real Firefox/ChatGPT case where both the focused wrapper and editable descendant expose an invalid caret while the empty editor is represented only by whitespace.

### Alterações
- If exactly one visible editable descendant is whitespace-only and has no valid selection/caret, treat it as an empty rich editor and replace only that whitespace via AT-SPI.
- Preserve the portal fallback for ambiguous descendants or any descendant containing meaningful draft text.
- Added regression coverage for invalid-caret whitespace descendants.
- Version bumped to 0.6.6.

### Testes
- `/usr/bin/python3 -B -m unittest -v test_desktop`: 16/16 passed.
- Active Bridge venv: `test_bridge test_security test_desktop_mcp`: 29 passed, 4 expected integration skips.
- `git diff --check`: clean.

### Estado
Ready for live Firefox/ChatGPT Unicode verification. No MCP tool/schema change.

## 2026-09-09 03:26 WEST — ChatGPT

### Tarefa
Add compact semantic desktop observation view

### Ficheiros alterados
- `mcp_server.py`
- `test_desktop_mcp.py`

### Alterações
Added a compact default view in the MCP layer that scans up to 400 AT-SPI elements internally, ranks useful interactive/context elements, suppresses structural wrapper noise, repairs parent references, exposes attention UI, preserves a full diagnostic mode, and prevents actions against IDs that were scanned internally but not exposed to the model.

### Motivo
Live Firefox/YouTube testing showed that the accessibility tree is rich but excessively noisy; structural section/panel wrappers can consume the observation budget before useful controls are surfaced.

### Testes
- /home/user/chatgpt-local-bridge/.venv/bin/python -m unittest -v test_desktop_mcp (8/8 passed)
- /home/user/chatgpt-local-bridge/.venv/bin/python -m unittest discover -v (42 tests OK, 8 expected skips)
- /usr/bin/python3 -B -m unittest -v test_desktop (16/16 passed)

### Estado
Staged and unit-tested; pending live Firefox validation before version bump/release.

### Observações
desktop_observe gains mode='compact'|'full' at the MCP schema level, so deployment requires plugin/catalog refresh. No worker, portal, permission or sandbox policy changes in this step.

## 2026-09-09 03:39 WEST — ChatGPT

### Tarefa
Relax compact desktop targeting with unique semantic locators

### Ficheiros alterados
- `mcp_server.py`
- `test_desktop_mcp.py`

### Alterações
Changed compact desktop targeting so the full internally observed snapshot remains authoritative. Direct element IDs from that snapshot may be acted on even if omitted from compact output, and desktop_act now accepts unique semantic locators resolved against hidden internal elements. Ambiguous or stale/unobserved targets are refused.

### Motivo
Compact output should reduce reasoning noise without forcing extra observations merely to expose a target that the Bridge already observed internally. Unique semantic locators preserve deterministic targeting while removing unnecessary friction.

### Testes
- 13/13 test_desktop_mcp passed in active Bridge venv
- 16/16 test_desktop passed with /usr/bin/python3
- 47-test full discovery passed with 8 expected integration skips
- git diff --check clean

### Estado
Staged and unit-tested; pending live Firefox validation before release/version bump.

### Observações
This supersedes the previous compact-view note that hidden internal IDs were blocked. Hidden targets remain constrained to the current snapshot; semantic locators must resolve to exactly one showing/sensitive target. Raw pointer policy and GNOME consent rules are unchanged.


## 2026-09-09 13:00 WEST — Codex

### Tarefa e motivo
Implement the authorized audit fixes in the existing Bridge: one authoritative desktop
snapshot, discover controls beyond the previous 400-node ceiling, deterministic scoped
locators, operation verification, managed broad-workspace shell jobs and useful diagnostics.
Preserved the pre-existing compact/locator work, current filesystem/network policy, portal
consent and editor integrations. No installer changes, Git commit or publication.

### Ficheiros alterados
`desktop_worker.py`, `desktop.py`, `desktop_semantics.py`, `mcp_server.py`, `bridge.py`,
`security.py`, `command_sessions.py`, `diagnostics.py`, `README.md`, this log and the
corresponding desktop/MCP/command/bridge tests and live acceptance scripts.

### Alterações
- Worker owns snapshot identity, retained ancestry, presentation, query and action matching;
  removed MCP-side snapshot cache. Existing serialized private pipe remains the concurrency model.
- Separate scan budgets from output limits; retain hidden intermediary structure and report
  incomplete scans explicitly. Query/pagination preserves snapshot identity. Scoped unique
  locators revalidate current target and ancestry immediately before acting.
- Typed MCP actions/locators/expectations; verify tabs/toggles/scroll and explicit target
  postconditions, return observed changes, stop on failed required confirmation.
- Bounded incremental stdout/stderr, background job handles, polling and owned-group cleanup;
  synchronous output also bounded. No project/task permission scoping was added.
- Retain bounded worker diagnostic stderr, best-effort credential redaction, opt-in process
  arguments and journal filtering before limit. Empty journal searches return zero entries.
- Version 0.6.7; catalogue adds desktop_query and command_session (28 exported tools).

### Testes e resultados
- System Python: 24 desktop/semantic tests passed.
- Venv full discovery: 48 tests OK, 10 environment/integration skips; subsequent journal
  empty-result regression: focused 19 tests OK, 1 integration skip.
- Host Bubblewrap suite: 21 tests OK, 1 systemd integration skip; includes live output,
  cancellation, timeout, large-output bounds and child cleanup.
- Real MCP stdio in a transient user service: catalogue 28, incremental shell session,
  GTK Unicode readback, stale-snapshot rejection and verified checkbox toggle passed.
- Real Firefox localhost fixture: 602 scanned nodes, late button e530 found despite compact
  output of 20, focused input confirmed, button effect confirmed by readback, fixture closed.
- Live journal empty-match check returned count 0. git diff --check clean before deployment.

### Limitações verificadas
Firefox on this host accepts both AT-SPI set_text and focused insertion without changing
even a plain HTML input; both live probes failed readback and stopped correctly. Focus did
not fix it. The passing Firefox action fixture uses prefilled text and is NOT proof of
Firefox text input. check_browser_mcp.py --text-probe preserves the failing replacement
probe. GTK Unicode input passed. ChatGPT rich-editor input, portal keyboard and Chrome
were not validated in this change. No ChatGPT message was sent. A blank Firefox window
created during an earlier data-URL experiment was left because later ownership was not
unambiguous; the named localhost fixture windows were closed.
ChatGPT must refresh its tool catalogue to discover the new schema/tools; local wire
acceptance is not proof of the hosted ChatGPT connector path. Deployment results follow.


### Instalação confirmada — 2026-09-09 13:02 WEST
Installed 16 reviewed source/test/documentation files in `/home/user/chatgpt-local-bridge`.
Pre-install source backup and manifest: `/home/user/chatgpt-local-bridge-backups/pre-v067-20260909T120107Z`.
Only `mcp-tunnel-chatgpt-local-bridge.service` was restarted (13:01:07 WEST). Service active,
healthz/readyz HTTP 200, installed MCP process 837617, cwd installed directory, actual
BRIDGE_WORKSPACE=/home/user. Installed source reports 0.6.7. A bare shell import uses
the source default workspace instead; this was not confused with the service environment.
Installed-copy MCP acceptance repeated successfully: 28 tools, shell session output,
GTK Unicode readback, stale rejection and checkbox verification. ChatGPT-hosted catalogue
refresh and full ChatGPT-editor/browser text acceptance remain unverified as noted above.
# 2026-09-09 — Isolated scratch editor and process-scoped observation

Added text-editor-scratch policy, fresh_data_directory launch support, and the
XDG_DATA_HOME application-environment entry. Live GNOME Text Editor 50.0 restored
existing session documents despite --standalone --new-window, so scratch launches now
receive fresh private application-data directories. The first test stopped before any
write; its raw diagnostic output was removed after detecting restored sensitive content.
No credential values are intentionally retained in this project or test report.

Added desktop_observe(process_id=pid), window process_id metadata, and retained process
scope for action readback. Added a focus no-op when the target already has the requested
focus, avoiding a failing redundant AT-SPI grab_focus call observed in the real editor.
The PID filter does not imply one window per process or guarantee compositor activation.

Validation: 26 desktop/semantic tests and 7 focused launch/MCP tests passed. Local MCP
wire test using the real GNOME editor passed: one blank isolated window, focused editor,
set_text('olá'), and exact subsequent AT-SPI readback. No message was submitted and no
pre-existing document was intentionally edited. No screenshot verification or hosted
ChatGPT test yet; actual inactive-window focus recovery remains unproven.

Installed the changed Bridge runtime files and scratch alias with backup at
/home/user/chatgpt-local-bridge-backups/scratch-20260909T181504. Installed MCP schema
contains process_id; read-only observation of the remaining test draft confirmed one
window and exact olá text. Local Dev Bridge healthz/readyz both return 200 and OpenAI
polling resumed successfully. Closed only the two earlier test-created editor instances.
All other host configuration was preserved. Browser MCP, Unity and Blender are unchanged. No commit/push.
# 2026-09-09 — GNOME 50 compositor window focus

User authorized implementing a GNOME backend after real AT-SPI window focus failed.
Inspected gnome-desktop-mcp as an architectural reference (its declared range stops
at GNOME 49) and the installed GNOME Shell 50.1 source/resources. Implemented an
original small extension rather than installing the full third-party MCP. No third-party
source was copied. New gnome_windows.py and the desktop worker bind PID + exact title
to one compositor ID and recheck identity before focusing. Existing AT-SPI observation
remains the final focus verifier; failed focus now stops a batch. Added backend status,
receipt and window-binding metadata and guidance for window-level focus.

Validation: 29 Python desktop/semantic/identity tests passed. The first isolated GNOME
test timed out during startup with inherited desktop settings. Explicit GNOME user
session and Wayland environment resolved the harness startup. On a separate GNOME
50.1 compositor, inactive-window and minimized-window recovery passed. D-Bus transport
passed as well via check_gnome_windows.js. Six MCP wrapper tests also passed.
These checks do not establish main-session
acceptance. The extension installed successfully; the current shell has not discovered
it, so enablement needs a new login. No shell restart/logout was performed automatically. Runtime changes installed with
backup at /home/user/chatgpt-local-bridge-backups/gnome-focus-20260909T185210.
Local Dev Bridge healthz/readyz returned 200. Backend availability correctly remains
false until the GNOME extension loads at login; existing AT-SPI remains available.
Other MCPs and credentials were not modified. No commit/push.

## 2026-09-09 — Main-session GNOME focus verified after reboot

After the user restarted the PC, confirmed GNOME extension ACTIVE, window backend
available=true, both browser services active, and Local Dev Bridge healthz/readyz 200.
Tested the installed Bridge through MCP stdio in the real user desktop. The first
attempt used unsupported expect.states.active and was rejected before writing; removed
that test argument and used the worker's built-in focus verification plus fresh reads.
The production code was not changed for this test correction.

Successful run created isolated scratch PIDs 17721 and 17854, wrote olá and segundo,
confirmed PID 17721 became inactive, and focused its observed window using backend
GNOME Shell window focus with verified=true. Replaced only its text with olá novamente;
readback confirmed the exact replacement and unchanged segundo in PID 17854. Closed
only the second test instance and left the first draft open. A blank draft from the
initial test also remains. No pre-existing documents edited or saved.

Updated README status. Hosted ChatGPT focus recovery, main-session minimized recovery
and screenshots remain pending. The earlier isolated GNOME minimized-window test passed.


## 2026-09-10 — Installed Bridge pointer regression baseline

Preserved pre-existing tracked/untracked source in a mode-0600 local archive under
`backups/before-pointer-tests-20260910-174025/`, with the baseline Git HEAD. No
credentials or configuration were printed or published; existing edits remain.
Added `check.sh`, coordinate, Browser orchestration and worker dispatch tests, plus
an isolated Chrome acceptance runner. Bound initial DOM rectangle, scroll and
visibility during calibration. Updated installed-suite instructions.

Validation: baseline virtualenv 49 tests / 10 skips; system GI 24 passed. Final
virtualenv 58 tests / 11 skips, system GI 30 passed; opted-in host security,
regression and command-session suite 21 passed. Chrome guard acceptance: 11
scenarios passed (10 expected refusals, one stable trusted browser click).
Read-only sandbox initially prevented test temporary directories; the authorized
host run passed. Browser fixture initially used an unsuitable element-evaluation
context; corrected it to a page expression and asserted guard installation plus
expected refusal messages to prevent false positives. No physical portal input
acceptance claimed; the final DOM-to-OS timing gap remains explicitly documented.

Post-deployment: restarted only `mcp-tunnel-chatgpt-local-bridge.service`;
`/healthz` and `/readyz` returned HTTP 200. `check_desktop_mcp.py` passed with
29 catalogued tools: command-session completion, Unicode write/readback,
expected stale-snapshot refusal, and locator checkbox verification in its owned
GTK fixture. A Firefox Snap AT-SPI cache AppArmor warning appeared without
failing the fixture; no sandbox/profile changes were made. Unity application
probe remained unavailable and Blender refused the application connection;
Browser catalogue responded, extension connectivity was not probed.


## 2026-09-10 — Explicit physical-click outcomes and reversible scope

The user supplied a live ChatGPT acceptance report: final hover succeeded, the
button moved in the final gap, and one OS click landed outside it (~42 ms after
mutation). This is user-reported physical evidence, not a rerun in this change.

`browser_desktop.py` now separates hover evidence, dispatch receipt and click
readback. Misses return target_missed; absent/malformed readback is unconfirmed.
Both return ok=false; lost dispatch receipts retain unknown execution rather than
throwing away ambiguity. Click verified remains false pending application-effect
verification. No click retries. The page clears earlier click evidence and
rechecks geometry just before dispatch, then retains the first trusted click.
This does not eliminate the DOM-to-OS race or distinguish competing input owners.

`mcp_server.py` preserves the structured outcome as MCP isError for failed or
uncertain operations. The new click_scope parameter defaults to unspecified and
refuses clicks before any transport unless the caller declares reversible. This
is a caller policy declaration for low-impact actions, not automatic page-risk
classification. Tool instructions forbid raw-input circumvention for consequential
actions. No Bridge configuration, installer or other MCP was changed.

Tests: 17 focused Python tests passed; full runner 65 tests / 11 expected skips,
plus 30 system-GI tests passed. Headless Chrome: 12 scenarios passed including a
controlled post-validation target move and retention of the first missed click.
The later synthetic browser click tests evidence retention only, not an automatic
Bridge retry. New physical GNOME acceptance remains separate. Docs describe the
new result contract and required ChatGPT catalogue refresh. Pre-edit checkpoint:
backups/before-click-outcomes-20260910-180359/source.tar.gz (private, mode 0600).

Deployment verification: stdio MCP catalogue exposed click_scope and a real
wire call without it returned the expected refusal before input. Restarted only
mcp-tunnel-chatgpt-local-bridge.service; /healthz and /readyz both returned 200.
ChatGPT-side catalogue refresh has not been performed by this session.


## 2026-09-10 — v0.7.0 source release preparation

User authorized commit, non-force push and release publication in the existing
private SomeGuySomewhereSometime/pc-mcp-integration repository. Remote master was
d4d96794aaa4a9bfddfff818aee08fe6054c2738; no remote releases/version tags existed.
Local version tags v0.6.0 through v0.6.6 are retained unchanged. v0.7.0 reflects
new click-scope compatibility requirements. Added the exact installed GNOME
extension source so the documented focus component can be restored. No installer,
Browser service or running editor configuration was changed. Browser MCP remains
a separate prerequisite, explicitly documented in README and release notes.

Release checks: 65 tests / 4 expected skips with host sandbox/systemd flags, 30
GI tests passed, 12 isolated Chrome scenarios passed. User's subsequent physical
ChatGPT acceptance is recorded separately in RELEASE_NOTES.md, including observed
miss and lost-readback behavior and remaining disposable tabs. Credential scan
found only the synthetic URL in a redaction test. Preserve the previous remote
master under baseline/published-before-v0.7.0 before advancing the branch.
