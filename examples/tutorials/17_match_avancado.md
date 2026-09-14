# 17 — Match avançado

Além do básico (`004_match.lum`): múltiplas opções num braço (`|`),
condição extra (`if`, o "guard") e abrir o valor por dentro
("destruturar", ex.: `Forma::Circulo(r)` pega o `r` de dentro).

```lum
fn classifica(n: i32) -> str {
    return match n {
        0 => "zero",
        1 | 2 => "pequeno",
        v if v < 0 => "negativo",
        _ => "outro",
    };
}

fn area(f: Forma) -> f64 {
    return match f {
        Forma::Circulo(r) => 3.14159 * r * r,
        Forma::Retangulo(w, h) => w * h,
        Forma::Ponto => 0.0,
    };
}
```

Ordem importa: o primeiro braço que casa vence. `_` por último.
Guards (`if`) refinam sem aninhar `if/else`.

## Exercícios

1. `http_status(code)`: 200–299 "ok", 400–499 "erro do cliente",
   500–599 "erro do servidor" — use `v if ...` para faixas.
2. Abra um `Ok` com par dentro (padrão dentro de padrão).
3. Reescreva `040_validador.lum` trocando cada `if` por um braço de `match`.
