# 10 — Strings na prática

`str` é UTF-8. Operações comuns (exemplos 008, 026–029):

```lum
fn main() {
    let s: str = "  Olá, Lumen!  ";
    // Sem espaços nas pontas e em maiúsculas.
    let limpa = str::upper(str::trim(s));
    println(limpa);
    let partes = str::split("a,b,c", ",");   // vec!["a", "b", "c"]
    println(str::join(partes, "-"));
    // `str::to_int` pode falhar: devolve `Ok(número)` ou `Err(texto)`.
    match str::to_int("42") {
        Ok(n) => println(str::from_int(n)),  // 42
        Err(e) => println("erro: " + e),
    }
    println(str::concat("a", "b"));          // "ab"
}
```

## Template simples

```lum
fn saudacao(nome: str) -> str {
    return str::concat("Olá, ", str::concat(nome, "!"));
}
```

Para múltiplas chaves, veja `028_template.lum` (varre `chaves`/`valores`).

## Exercícios

1. `eh_palindromo` (lê igual de trás para frente). Dica: compare a
   primeira letra com a última usando `str::len` + `while`, andando
   das pontas para o centro (não existe `s[i]`; use as funções `str::*`).
2. Contador de vogais: para cada letra `c`, use
   `match c { "a" | "e" | "i" | "o" | "u" => ... }`.
3. Leitor de `chave=valor` por linha (`029_csv.lum` como modelo:
   quebre por `"\n"`, depois cada linha por `"="`).
