# 09 — Complexidade sem mistério

Complexidade = "quantas operações o programa faz quando a entrada cresce".
`n` é o tamanho da entrada (ex.: quantos números há no vetor).

| Padrão | Custo | Exemplo |
|---|---|---|
| um `while` até `n` | `O(n)` | `soma` em 034 |
| dois `while` aninhados | `O(n²)` | bubble sort |
| divide pela metade | `O(log n)` | busca binária |
| tabela + reaproveita | `O(n)` | `fib_memo` em 033 |

## Memoização

Trocar recomputação por memória: o vetor `memo` em `033_fib_memo.lum`
guarda `-1` para "não calculado". De exponencial para linear com um vetor.

## Exercícios

1. Meça (na mão) comparações do bubble vs. inserção em 10 elementos.
2. Mostre que `fib(30)` recursivo puro faria ~2M de chamadas.
3. Quando memoizar **não** ajuda? (dica: entradas que não se repetem)
