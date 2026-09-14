# Tutorial 03 — Struct, enum e `match` (~1h)

> Nível 2. Exemplos: `004_match.lum`, `005_struct.lum`, `006_enum.lum`.

## 1. Struct + `impl`

```lum
/// Ponto no plano.
struct Ponto { x: f64, y: f64 }

impl Ponto {
    fn novo(x: f64, y: f64) -> Ponto {
        return Ponto { x: x, y: y };
    }
    fn norma(self) -> f64 {
        return math::sqrt(self.x * self.x + self.y * self.y);
    }
}

fn main() {
    let p = Ponto::novo(3.0, 4.0);
    println(str::from_float(p.norma()));  // 5
}
```

- Construção: `Ponto { x: 1.0, y: 2.0 }` monta o valor; `p.x` lê o campo.
- `Ponto::novo(...)` é função da "fábrica" (chamada com `::`).
  `p.norma()` é método do valor: recebe `self` (o próprio `p`) e usa `.`.

## 2. Enum com payload

```lum
enum Forma { Circulo(f64), Retangulo(f64, f64), Ponto }

fn area(f: Forma) -> f64 {
    return match f {
        Forma::Circulo(r) => 3.14159 * r * r,
        Forma::Retangulo(w, h) => w * h,
        Forma::Ponto => 0.0,
    };
}
```

Variantes com dados junto ("payload", ex.: `Circulo(1.0)`) e sem dados
(ex.: `Ponto`) convivem. `Option<T>` (`Some`/`None`, "tem valor / vazio")
e `Result<T, E>` (`Ok`/`Err`, "deu certo / deu erro") são enums prontos.

## 3. `match` a fundo

```lum
fn rotulo(n: i32) -> str {
    return match n {
        0 => "zero",
        // `|` significa "ou": vale para 1 ou 2.
        1 | 2 => "pequeno",
        // `v if ...` testa uma condição extra (chamada de "guard").
        v if v < 0 => "negativo",
        // `_` é o "coringa": pega todo o resto. Deixar o coringa no
        // final torna o `match` "exaustivo" (cobre todos os casos).
        _ => "médio",
    };
}
```

Ordem importa: o primeiro braço que combina vence. A condição extra
(`guard`) não conta como cobertura — o `_` final continua obrigatório.

## 4. Exercícios

1. Adicione `Triangulo(b, h)` a `Forma` e cubra no `match` (o
   compilador acusa o braço faltante — teste!).
2. Crie `enum Moeda { Real(i32), Dolar(f64) }` + `em_reais(m: Moeda)`.
3. Rode `python3 conformance/suite.py --filter match` e
   `--filter struct_enum`: são os casos `MAT-*` e `ST-*`.

Próximo: `04_colecoes_strings_io.md`.
