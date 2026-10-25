#!/bin/bash
# Registra o AstroMCP no Claude Code (escopo do usuário) lendo as credenciais do bot do TNS
# de ~/Work/CacaSN/tns.json, sem mostrar a chave na tela.
# uso: bash ~/Work/AstroMCP/scripts/registrar_claude.sh
set -euo pipefail
CFG="${TNS_JSON:-$HOME/Work/CacaSN/tns.json}"
ID=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['bot_id'])" "$CFG")
NOME=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['bot_name'])" "$CFG")
CHAVE=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['api_key'])" "$CFG")
claude mcp remove astromcp -s user >/dev/null 2>&1 || true
claude mcp add astromcp -s user \
  -e TNS_BOT_ID="$ID" -e TNS_BOT_NAME="$NOME" -e TNS_API_KEY="$CHAVE" \
  -- uv run --directory "$HOME/Work/AstroMCP" astromcp >/dev/null
echo "AstroMCP registrado. Conferindo conexão:"
claude mcp list 2>&1 | grep -i astromcp || echo "(não apareceu na lista — veja 'claude mcp list')"
