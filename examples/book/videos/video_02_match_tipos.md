# Vídeo 02 — `match` e tipos: o coração do Lumen (~15 min)

> Público: já rodou o hello. Meta: ler/escrever `match` exaustivo e
> modelar com `struct`/`enum`. Arquivos: `004_match`, `005_struct`, `006_enum`.

## 0:00–2:00 — Por que `match`?

- [FALA] "`if` decide booleano; `match` decide formato. E o
  compilador cobra todos os casos."
- [TELA] `classifica` de `004_match.lum` rodando 5 entradas.

## 2:00–6:00 — Padrões, na prática

- [TELA] evolui ao vivo: literal → `1 | 2` → guard `v if v < 0` → `_`.
- [FALA] "Primeiro braço que casa vence; guard não conta para
  exaustividade — o `_` é obrigatório."
- [TELA] remove o `_`, mostra o erro, recoloca.

## 6:00–10:30 — Enums com payload

- [TELA] `enum Forma` + `area` de `006_enum.lum`.
- [FALA] "A variante carrega os dados; o `match` destrutura e liga."
- [TELA] adiciona `Triangulo(b, h)` e deixa o compilador apontar o
  braço faltante — momento "uau".

## 10:30–13:30 — Structs e métodos

- [TELA] `Ponto` + `impl` de `005_struct.lum`; `p.norma()` → 5.
- [FALA] "`::` é da família (associado); `.` é do objeto (instância)."

## 13:30–15:00 — Encerramento + CTA

- [FALA] "Desafio: `enum Moeda` + `em_reais`. Gabarito no livro,
  cap. 3. Próximo vídeo: o projeto async com HTTP e SQLite."
