# 13 — Programas de linha de comando

Todo CLI tem três partes: argumentos → configuração → execução
(`016_cli_json.lum`, `035_config.lum`).

```lum
use std::io;

fn run(caminho: str) {
    println("abrindo: " + caminho);
}

fn main() {
    // `io::args()` devolve a lista de argumentos; a posição 0 é o nome
    // do programa. O `match` não aceita padrão de lista `[a, b]`, então
    // contamos e lemos por posição com `vec::len` + `vec::get`.
    let args = io::args();
    if vec::len(args) == 2 {
        match vec::get(args, 1) {
            Some(caminho) => run(caminho),
            None => println("uso: app <arquivo>"),
        }
    } else {
        println("uso: app <arquivo>");
    }
}
```

## Config

```lum
struct Config { entrada: str, saida: str, verboso: bool }

fn padrao() -> Config {
    return Config { entrada: "-", saida: "-", verboso: false };
}
```

## Exercícios

1. `--verboso` e `--saida <arq>`: percorra `args` com `while` e compare
   cada item com `==` (passo a passo, sem biblioteca de CLI).
2. Códigos de saída: `0` deu certo, outro número deu erro (o `main`
   dos exemplos imprime; o número de saída é definido pelo runner).
3. Leia o `lumen.toml` do projeto com `fs::read_arquivo` e imprima a
   linha do `nome` (seção `[package]`).
