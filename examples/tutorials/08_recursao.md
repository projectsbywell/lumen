# 08 — Recursão

Toda recursão precisa de: caso base + passo que encolhe a entrada.

```lum
fn fat(n: i32) -> Result<i32, str> {
    if n < 0 {
        return Err("n negativo");
    }
    if n <= 1 {
        return Ok(1);
    }
    match fat(n - 1) {
        Ok(v) => return Ok(n * v),
        Err(e) => return Err(e),
    }
}
```

## Quando trocar por laço

Fibonacci chamando a si mesmo duas vezes explode (tempo "exponencial":
dobra a cada nível); a versão com caderno de anotação ("cache", `033`)
ou com laço (`003`) cresce devagar ("linear"). Regra prática: recursão
para formas que se repetem dentro de si (árvores, `023_arvore.lum`);
laço para contar.

## Exercícios

1. `soma_ate(n)` nas duas versões (chamando a si mesma e com `while`); compare.
2. Busca em árvore binária (dica: cada filho pode existir ou não:
   use `Option<Nodo>` + `match`).
3. Busca por largura ("BFS": visitar por camadas) com fila
   (`024_grafo_bfs.lum`) — por que fila e não recursão? (Resposta curta:
   a ordem de visita é por camada, e a fila guarda "quem vem a seguir".)
