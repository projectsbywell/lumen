# 15 — Concorrência com async/await

Concorrência = fazer dois downloads ao mesmo tempo em vez de um após o
outro. `async fn` é uma função que pode pausar esperando a rede;
`spawn` agenda a execução; `await` espera e pega o resultado
(exemplos 015, 042).

```lum
async fn baixa(url: str) -> str {
    let r = http::get(url)?;
    return r.corpo;
}

fn main() {
    let a = spawn baixa("https://a.exemplo.com");
    let b = spawn baixa("https://b.exemplo.com");
    println(await a);
    println(await b);
}
```

Os dois downloads andam juntos; os `await`s resolvem na ordem do `spawn`.

## Regras

- `await` só funciona no valor que o `spawn` devolveu (a "senha"/handle).
  Cada handle é usado uma vez.
- `async` sem pausa dentro se comporta como função comum.
- `?` dentro de `async` transforma o erro em `Err`; trate com `match`
  após o `await` (ou repasse com `?` se a função atual devolve `Result`).

## Exercícios

1. Baixe 3 URLs e imprima na ordem de chegada (dica: `await` alternado).
2. `com_retry` assíncrono (junte 038 + `spawn`).
3. Cache compartilhado entre tarefas (`037_cache.lum` + `spawn`).
