# 14 — Seu primeiro projeto

Juntando tudo: estrutura, módulos e build (`05_projeto.md` continua aqui).

```
meuapp/
  lumen.toml
  src/main.lum
  src/calc.lum
  testes/teste_calc.lum
```

## `lumen.toml`

```toml
[package]
nome = "meuapp"
versao = "0.1.0"

[tasks.bom]
cmd = "python3 compiler/lumenc.py src/main.lum ir"
```

Build com o sistema da plataforma:

```sh
python3 tools/build/lumen_build.py
```

## Módulos

Um módulo ("mod") é um arquivo `.lum`. `use std::io;` no topo libera os
nomes daquele módulo. Convenções de nome: tipos com inicial maiúscula
("PascalCase", ex.: `Config`); funções com minúsculas e `_`
("snake_case", ex.: `padrao`). Função que pode falhar devolve `Result`
— nunca sinalize erro com string vazia nem `-1` escondido ("mágico").

## Exercícios

1. Separe `031_calculadora.lum` em `calc.lum` + `main.lum`.
2. Adicione task `teste` que roda a suíte de conformidade.
3. Publique no registry local (`tools/pkg/registry.py`).
