# 07 — Estruturas de dados

`vec` (lista), pilha, fila e mapa: as quatro peças básicas
(exemplos 019–021, 039).

## Pilha e fila

Pilha é "último a entrar, primeiro a sair" (como pratos empilhados);
fila é "primeiro a entrar, primeiro a sair" (como fila de banco).

```lum
struct Pilha { itens: Vec }

impl Pilha {
    fn nova() -> Pilha {
        return Pilha { itens: vec![] };
    }
    fn push(self, v: i32) -> Pilha {
        return Pilha { itens: vec::push(self.itens, v) };
    }
    fn tamanho(self) -> i32 {
        return vec::len(self.itens);
    }
}

fn main() {
    let p = Pilha::nova();
    let p2 = p.push(10);
    println(str::from_int(p2.tamanho()));
}
```

Fila usa o mesmo `vec` com um número guardando a posição da "cabeça"
em vez de remover do início (remover do início desloca todo o resto e
custa proporcional ao tamanho — `O(n)`).

## Mapa como dicionário

```lum
fn main() {
    // Dicionário nome → nota.
    let mut m = map!{ "ana": 9 };
    map::insert(m, "bia", 7);
    match map::get(m, "ana") {
        // `v` é número: converta para texto antes de imprimir.
        Some(v) => println(str::from_int(v)),
        None => println("ausente"),
    }
}
```

## Exercícios

1. Implemente `Fila` com `inicio: i32` (índice, sem `shift`).
2. Faça `tabela_hash` com 8 baldes e colisões por lista.
3. Pagine um vetor de 10 em páginas de 3 (`039_paginacao.lum`).
