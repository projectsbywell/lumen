# Tutorial 02 — Funções, tipos e controle (~45 min)

> Nível 1. Exemplos: `002_fatorial.lum`, `003_fibonacci.lum`, `010_math.lum`.

## 1. Funções

```lum
/// Soma dois inteiros.
fn soma(a: i32, b: i32) -> i32 {
    return a + b;
}
```

- Parâmetros e retorno com tipo escrito (`a: i32`). `pub` significa
  "pública" (pode ser usada de fora do arquivo).
- `return` explícito; só escrever o valor no final **não** retorna.
- Chamada: `soma(2, 3)` devolve `5`.

## 2. Tipos básicos

| Tipo | Exemplos |
|---|---|
| `i32`, `i64` | `42`, `-7`, `1_000` |
| `f64` | `3.14`, `2.0` (`/` em `i32` trunca; em `f64` não) |
| `bool` | `true`, `false` |
| `char` | `'x'` (aspas simples!) |
| `str` / `String` | `"texto"` (`String` coage para `str`) |
| `()` | `()` (unit, "nada") |

```lum
fn main() {
    // `let` cria uma variável imutável (não muda depois).
    // O tipo `i32` (inteiro de 32 bits) foi descoberto sozinho.
    let x = 5;
    // `mut` libera a variável para mudar. Aqui o tipo foi escrito à mão.
    let mut y: i32 = 0;
    y = y + 1;
    // Valor fixo que nunca muda: por convenção, nome em MAIÚSCULAS.
    let max: i32 = 100;
    println(str::from_int(x + y + max));
}
```

## 3. Controle: `if`, `for`, `while`

```lum
fn mostra(n: i32) {
    // `if/else` escolhe um dos dois caminhos.
    if n < 0 {
        println("negativo");
    } else {
        println("ok");
    }
}

fn main() {
    mostra(-3);
    // `for i in 0..5` repete com i = 0, 1, 2, 3, 4 (o 5 fica de fora).
    for i in 0..5 {
        println(str::from_int(i));
    }
    let mut y: i32 = 0;
    // `while` repete enquanto a condição for verdadeira.
    while y < 10 {
        y = y + 1;
    }
    println(str::from_int(y));
}
```

Um "range" (intervalo) `0..5` exclui o 5; `0..=5` inclui o 5.
Ranges só funcionam com `i32`.

## 4. Erros com `Result` e `?`

```lum
fn fat(n: i32) -> Result<i32, str> {
    if n < 0 {
        return Err("n negativo");
    }
    if n <= 1 {
        return Ok(1);
    }
    let sub = fat(n - 1)?;   // Err aqui retorna da função
    return Ok(n * sub);
}
```

Regra prática: se o programa pode se recuperar do erro (ex.: número
inválido), devolva `Result` e use `?` para repassar. `panic("msg")`
é só para bugs — ele encerra o programa.

## 5. Exercícios

1. Escreva `fib_iter` sozinho (gabarito em `003_fibonacci.lum`).
2. Faça `div(a: i32, b: i32) -> Result<i32, str>` que recusa `b == 0`.
3. Rode `python3 conformance/suite.py --filter tipos` e leia os casos
   `TIP-*`: cada um é uma regra desta aula virando teste.

Próximo: `03_struct_enum_match.md`.
