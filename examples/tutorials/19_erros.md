# 19 — Erros como valores

Sem exceções: `Result<T, E>` + `?` (002, 009, 012, 038).

```lum
fn prepara(db: sqlite::Db) -> Result<i32, str> {
    // `?`: se der `Ok`, continua; se der `Err`, retorna o erro na hora.
    sqlite::exec(db, "CREATE TABLE u (nome TEXT)")?;
    sqlite::exec(db, "INSERT INTO u VALUES ('ana')")?;
    return Ok(1);
}

fn main() {
    match sqlite::abrir(":memory:") {
        Ok(db) => match prepara(db) {
            // `n` é número: converta antes de imprimir.
            Ok(n) => println(str::from_int(n)),
            Err(e) => println(str::concat("falhou: ", e)),
        },
        Err(e) => println(str::concat("não abriu o banco: ", e)),
    }
}
```

`?` abre o `Ok` ou devolve o `Err` na hora — evita `if` dentro de `if`
("pirâmide").

## Regras

- Função que pode falhar retorna `Result`; nunca "código mágico".
- `main` decide: trata com `match` ou propaga com `?`.
- Teste os dois lados (tutorial 16).

## Exercícios

1. `divide(a, b)` com `Err("divisão por zero")` + retry (038).
2. Pipeline ler→parsear→salvar com `?` em cada etapa (048).
3. Converta um `panic!` hipotético em `Result` sem quebrar chamadores.
