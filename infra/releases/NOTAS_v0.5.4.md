# Notas da release — Lumen v0.5.4 (2026-09-14)

Release de **integração**: versões unificadas, docs sincronizados e um
gate novo no CI. **Sem mudança de semântica** — código escrito para
v0.5.x compila e roda igual.

> Documento de apoio do GitHub Release v0.5.4 (a tag se cria/push manual:
> `git tag v0.5.4 && git push --tags` — sem push nesta sessão).
> Resumo executivo em `../RELEASES.md` (seção `## v0.5.4`).

## O que mudou (só integração/docs/CI)

- **Versões unificadas em `0.5.4`**: `lumen.toml`, `pyproject.toml`
  (com `Repository` corrigido para
  `https://github.com/projectsbywell/lumen`),
  `lumen_cli.py` (`__version__` + docstring), `conformance/suite.py`
  (`SPEC_VERSION` + `SUITE_VERSION`), `docs/gen.py` (`SPEC_VERSION`),
  `spec/SPEC.md` + `EBNF.md` + `TIPOS.md` + `SEMANTICA.md`.
- **`docs/API.md` regenerado** com `docs/gen.py` (determinístico; diff só
  na linha de versão).
- **Honestidade da suíte**: nota em `spec/SPEC.md` §8 — a suíte 50/50 é
  um subset v0.1 (não cobre GC/async/traits macroscopicamente; itens 5/9
  dos revisores, ver `LIMITACOES.md`).
- **`SHA256SUMS.txt` com SHAs reais** da tag v0.5.3 (última publicada;
  sdist/wheel publicados = build Windows; variantes Linux/macOS
  preservadas como registro no cabeçalho do arquivo).
- **Gate CI `Run examples (001-004)`** (`infra/ci.yml` + espelho
  `.github/workflows/ci.yml`, idênticos): roda `compiler/run.py` em
  `001_hello` (`Olá, Lumen!`), `002_fatorial` (`5! = 120`),
  `003_fibonacci` (fib 0–34), `004_match`
  (zero/pequeno/negativo/grande/médio) e falha se divergir.
  **Fica vermelho em 002/004 até o Fix A pousar (é o propósito).**
- **Baratas**: passo `Testes unitários (v0.5)` (lista agora inclui
  `tools.fmt.test_fmt`); smoke 66→70 exemplos; `docker-entrypoint.py`
  com a mesma lista de testes do CI; `Dockerfile` v0.5 + nota PyInstaller;
  `LIMITACOES.md` (v0.5.x) e `REVISORES.md` com marcas de histórico.

## Assets esperados (quando a tag v0.5.4 for lançada)

| OS | Artefato | Origem |
|---|---|---|
| todos | `lumen-0.5.4.tar.gz` (sdist) | `python3 -m build` |
| todos | `lumen-0.5.4-py3-none-any.whl` (wheel) | `python3 -m build` |
| Linux (x86_64) | `lumen-linux` | PyInstaller `--onefile` |
| Windows (x86_64) | `lumen.exe` | PyInstaller `--onefile` |
| macOS | `lumen-macos` | PyInstaller `--onefile` |
| todos | `SHA256SUMS-<OS>.txt` | `sha256sum dist/*` (job `build-release`) |

Enquanto a v0.5.4 não é tagueada, os únicos SHAs publicados são os da
**v0.5.3** (`SHA256SUMS.txt` neste diretório).

## Como instalar (última publicada, v0.5.3)

### Via pip (Python 3.8+, sem dependências)

```sh
pip install .                                    # a partir do repo
pip install lumen-0.5.0-py3-none-any.whl         # do asset baixado
```

### Binário nativo (sem Python instalado)

```sh
gh release download v0.5.3 --repo projectsbywell/lumen -D ./lumen-dl
cd ./lumen-dl && sha256sum -c "$OLDPWD/infra/releases/SHA256SUMS.txt"
chmod +x lumen-linux && sudo mv lumen-linux /usr/local/bin/lumen
```

(No Windows: `certutil -hashfile lumen.exe SHA256` e compare com
`SHA256SUMS.txt`.)

## Smoke da instalação

```sh
lumen --help                       # uso dos subcomandos
lumen version                      # lumen 0.5.4
lumen build examples/001_hello.lum ir   # .lum -> IR (stdout)
lumen run examples/001_hello.lum        # compila e executa na VM
lumen test                          # runner @test no diretório
lumen conformance                   # suíte 50/50 (precisa do repo)
```

## Breaking changes

Nenhum — semântica e APIs intactas nesta versão.
