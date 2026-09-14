# 06 — Algoritmos básicos em Lumen

Ordenar é colocar em ordem; buscar é achar um item. Vamos usar o básico
da linguagem: `vec` (lista), `while` (repete) e `match` (escolhe).

## Bubble sort

A ideia: compare vizinhos e troque quem está fora de ordem. Repita até
ordenar. Em Lumen não existe `v[i]`; lemos com `vec::get` (devolve
`Some(valor)` ou `None`) e montamos o resultado com `vec::push`.

```lum
fn troca(v: Vec<i32>, i: i32, j: i32) -> Vec<i32> {
    let mut novo = vec![];
    let mut k: i32 = 0;
    let n = vec::len(v);
    while k < n {
        let atual = match vec::get(v, k) {
            Some(x) => x,
            None => 0,
        };
        if k == i {
            let outro = match vec::get(v, j) {
                Some(y) => y,
                None => 0,
            };
            novo = vec::push(novo, outro);
        } else {
            if k == j {
                let outro = match vec::get(v, i) {
                    Some(y) => y,
                    None => 0,
                };
                novo = vec::push(novo, outro);
            } else {
                novo = vec::push(novo, atual);
            }
        }
        k = k + 1;
    }
    return novo;
}

fn ordena(v: Vec<i32>) -> Vec<i32> {
    let mut res = v;
    let n = vec::len(res);
    let mut i: i32 = 0;
    while i < n {
        let mut j: i32 = i + 1;
        while j < n {
            let a = match vec::get(res, j - 1) {
                Some(x) => x,
                None => 0,
            };
            let b = match vec::get(res, j) {
                Some(x) => x,
                None => 0,
            };
            if a > b {
                res = troca(res, j - 1, j);
            }
            j = j + 1;
        }
        i = i + 1;
    }
    return res;
}
```

## Busca binária

Exige vetor ordenado. Compara o meio e descarta metade por iteração —
`O(log n)`. Veja `018_busca_binaria.lum`.

## Exercícios

1. Transforme o bubble em `ordena_decrescente` (troque `a > b` por `a < b`).
2. Conte comparações com um contador `mut` (ex.: `let mut cont: i32 = 0;`
   some 1 a cada `if`) e imprima com `str::from_int`.
3. Implemente busca linear (olhe item por item) e compare o número de
   passos num vetor de 100 itens como `vec![1, 2, 3]`.
