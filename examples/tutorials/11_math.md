# 11 — Matemática e números

`i32` (inteiro, ex.: `42`), `f64` (decimal, ex.: `3.14`) e o módulo
`math` (exemplos 010, 031–034). Para usar, escreva `use std::math;`
no topo: isso libera os nomes `math::...`.

```lum
use std::math;

fn main() {
    let raiz = math::sqrt(2.0);
    println(str::from_float(raiz));
    let pot = math::pow(2.0, 10.0);
    println(str::from_float(pot));
    // `math::fat` pode falhar (n negativo): devolve `Ok` ou `Err`.
    match math::fat(6) {
        Ok(v) => println(str::from_int(v)),  // 720
        Err(e) => println(e),
    }
}
```

## Inteiros vs. floats

`/` de inteiros trunca (`7 / 2 == 3`); converta com `x as f64`
quando precisar de fração. Comparações encadeadas usam `match` com guards:

```lum
fn sinal(x: f64) -> str {
    return match x {
        v if v < 0.0 => "negativo",
        v if v > 0.0 => "positivo",
        _ => "zero",
    };
}
```

## Exercícios

1. Juros compostos: `montante(c, i, n)` com `math::pow`.
2. `eh_primo` até 100 e a lista (`032_primalidade.lum`).
3. Média/desvio de um `vec` (`034_estatistica.lum`).
