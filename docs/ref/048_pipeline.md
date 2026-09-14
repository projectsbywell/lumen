# `examples/001-050/048_pipeline.lum`

048 — Pipeline de dados com `async`, `spawn` e `await`.

Cada estágio do pipeline é uma função assíncrona; estágios
rodam concorrentemente com `spawn` e o resultado é
coletado com `await`.
Estágio 1: baixa dados de uma URL.
Estágio 2: transforma os dados (simula parse).
Estágio 3: persiste o resultado.
Executa o pipeline completo: baixa, transforma e persiste.

## Índice

- `fn` [main](#main)
- `fn` [testa_pipeline_assinatura](#testa-pipeline-assinatura)

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_pipeline_assinatura

```lum
fn testa_pipeline_assinatura() {
```

Atributos: `#[test]`

_Sem documentação `///`._
