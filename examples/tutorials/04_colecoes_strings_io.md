# Tutorial 04 — Coleções, strings e IO (~1h)

> Nível 3. Exemplos: `007_colecoes.lum`, `008_strings.lum`,
> `009_io.lum`, `010_math.lum`.

## 1. `Vec<T>`

```lum
fn dobrar_um(x: i32) -> i32 {
    return x * 2;
}

fn eh_par(x: i32) -> bool {
    return x % 2 == 0;
}

fn main() {
    let nums = vec![1, 2, 3, 4, 5];
    // `vec![]` cria um vetor vazio; `vec::push` devolve o vetor com
    // o item novo (por isso guardamos de volta em `nomes`).
    let mut nomes = vec![];
    nomes = vec::push(nomes, "ana");
    // `vec::map` transforma cada item; `vec::filter` mantém só os que
    // passam no teste. Ambos devolvem um vetor novo e recebem o nome
    // de uma função pronta (sem parênteses).
    let dobrados = vec::map(nums, dobrar_um);
    let pares = vec::filter(nums, eh_par);
    println(str::from_int(vec::len(pares)));
    println(str::from_int(vec::len(dobrados)));
}
```

`vec::map`/`filter` recebem uma função e devolvem um vetor novo.
Prefira essa forma pronta ao `while` com `mut`; só troque pelo laço
manual se medir e provar que ele é o gargalo (parte lenta).

## 2. `Map<K, V>`

```lum
fn main() {
    // `map!{...}` cria um dicionário chave → valor.
    let mut notas = map!{ "ana": 9, "bia": 7 };
    map::insert(notas, "cid", 10);
    // `get` devolve `Some(valor)` se a chave existe, ou `None`.
    match map::get(notas, "ana") {
        Some(v) => println(str::from_int(v)),
        None => println("sem nota"),
    }
}
```

`map::has(notas, chave)` testa se a chave existe; `map::remove(notas,
chave)` tira a entrada e devolve o valor.

## 3. Strings UTF-8

```lum
fn main() {
    // `str::len` conta letras (caracteres), não bytes.
    println(str::from_int(str::len("olá")));  // 3
    println(str::upper("lumen"));             // "LUMEN"
    let partes = str::split("a,b", ",");     // vec!["a", "b"]
    println(str::join(partes, " | "));       // junta com separador
    println(str::trim("  x  "));             // "x" (tira espaços)
    println(str::from_int(42));              // "42" (número vira texto)
}
```

`+` junta textos (`str`/`String`) em qualquer combinação.

## 4. IO e arquivos

```lum
use std::io;
use std::fs;

fn main() {
    // Cada operação pode falhar, então devolve `Result`.
    // `?` repassa o erro; o `match` no final trata tudo num lugar só.
    match io::read_line() {
        Ok(linha) => println("voce digitou: " + linha),
        Err(e) => println("erro no teclado: " + e),
    }
    match fs::read_arquivo("dados.txt") {
        Ok(texto) => println(texto),
        Err(e) => println("erro no arquivo: " + e),
    }
}
```

## 5. Exercícios

1. Leia `dados.txt`, conte linhas com `str::split(texto, "\n")`.
2. Monte um `Map` palavra→contagem (desafio: use `match` no `get`).
3. Rode a suíte `--filter stdlib` e confira `STD-01/02/05/06`.

Próximo: `05_projeto.md` — o projeto guiado.
