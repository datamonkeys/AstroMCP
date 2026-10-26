# Como publicar o AstroMCP (passo a passo para o Louis)

Tudo abaixo é feito por você; nada disto foi executado ainda. Trabalhe a partir da branch `publicar`
(depois de conferida, faça o merge em `main`: o repositório público deve nascer da `main`).

```bash
cd ~/Work/AstroMCP
git checkout main && git merge --ff-only publicar
git worktree remove .claude/worktrees/publicar   # opcional, depois do merge
```

## 0. Checagem antes de qualquer push (regra "verificar antes de subir")

```bash
cd ~/Work/AstroMCP
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict
uv run pytest                                  # offline; os de integração ficam de fora
uv run pytest -m integration                   # opcional: consultas reais (TNS precisa das credenciais)

# build + instalação limpa + MCP initialize via stdio
rm -rf dist && uv build
rm -rf /tmp/am-venv && uv venv -p 3.11 /tmp/am-venv
uv pip install -p /tmp/am-venv dist/*.whl
/tmp/am-venv/bin/python scripts/smoke_stdio.py /tmp/am-venv/bin/astromcp   # espera "14 tools"

# nota pre.dev num clone limpo (meta: A >= 85)
rm -rf /tmp/astromcp-clone && git clone -q --branch main ~/Work/AstroMCP /tmp/astromcp-clone
node ~/Desktop/temp/predev-quality-score/score.mjs collect /tmp/astromcp-clone
```

Só siga se tudo estiver verde.

## 1. Criar o repositório no GitHub e subir

```bash
cd ~/Work/AstroMCP
gh repo create louisperner/AstroMCP --public --source=. --push \
  --description "MCP server: read-only access to public astronomy archives (TNS, SIMBAD, VSX, Gaia, TESS, ZTF, Rubin)"
gh repo edit louisperner/AstroMCP --add-topic mcp --add-topic astronomy --add-topic model-context-protocol --add-topic transients
```

## 2. Conferir o CI

```bash
gh run watch --repo louisperner/AstroMCP     # ou: gh run list --repo louisperner/AstroMCP
```

Os 3 jobs (Python 3.11, 3.12, 3.13) precisam ficar verdes; o badge no README passa a funcionar.

## 3. Publicar no PyPI

1. Confirme que o nome continua livre: `curl -s -o /dev/null -w "%{http_code}\n" https://pypi.org/pypi/astromcp/json`
   (404 = livre; em 25/10/2026 estava livre).
2. Crie a conta / ative 2FA em https://pypi.org e gere um token em
   https://pypi.org/manage/account/token/ (escopo "Entire account" na primeira vez; depois do primeiro upload,
   troque por um token só do projeto `astromcp`).
3. Publique:

```bash
cd ~/Work/AstroMCP
rm -rf dist && uv build
UV_PUBLISH_TOKEN=pypi-... uv publish
```

4. Teste de fora: `uvx astromcp` deve subir (Ctrl+C para sair) e
   `uvx --from astromcp python -c "import astromcp; print(astromcp.__version__)"` deve imprimir 0.1.0.
5. Marque a versão: `git tag v0.1.0 && git push origin v0.1.0 && gh release create v0.1.0 --notes-file CHANGELOG.md`

## 4. Publicar no registro oficial de servidores MCP

O `server.json` já está pronto (nome `io.github.louisperner/astromcp`, pacote PyPI `astromcp` 0.1.0). O registro
confere a posse do pacote procurando `mcp-name: io.github.louisperner/astromcp` no README publicado no PyPI
(já está lá num comentário HTML), então só faça isto **depois** do passo 3.

```bash
brew install mcp-publisher
mcp-publisher login github        # abre o fluxo do GitHub; precisa ser a conta louisperner
mcp-publisher publish             # na pasta do projeto, lê ./server.json
curl -s "https://registry.modelcontextprotocol.io/v0/servers?search=io.github.louisperner/astromcp"
```

## 5. Atualizar o seu Claude Code para usar o pacote publicado (opcional)

`scripts/registrar_claude.sh` registra usando o checkout local (`uv run --directory`). Para usar o PyPI:
`claude mcp add astromcp -s user -e TNS_BOT_ID=... -e TNS_BOT_NAME=... -e TNS_API_KEY=... -- uvx astromcp`.

## Próximas versões

Mude a versão em `pyproject.toml`, `src/astromcp/__init__.py` e nos dois campos `version` do `server.json`,
registre no `CHANGELOG.md`, rode a checagem do passo 0, e repita 3 e 4.
