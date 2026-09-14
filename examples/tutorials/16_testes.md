# 16 — Testes do seu código

Marque com `#[test]` e rode o runner (`013_teste.lum`):

```lum
fn soma(a: i32, b: i32) -> i32 {
    return a + b;
}

#[test]
fn testa_soma() {
    assert_eq(soma(2, 3), 5);
    assert_eq(soma(-1, 1), 0);
}
```

```sh
python3 tools/test/lumen_test.py .
```

## Boa cobertura, barato

"Cobertura" = quanto do código os testes exercitam.

1. Um `#[test]` por função pública (a linha `#[test]` marca a função
   como teste; o runner a executa).
2. Casos de borda (extremos): lista vazia, zero, negativo, valor máximo.
3. Para `Result`: teste o caminho `Ok` **e** o caminho `Err`.

## Exercícios

1. Testes para `categoria` (040) cobrindo as 5 faixas + negativo.
2. Teste de `pagina` (039) com página além do fim.
3. Teste que falha de propósito e leia o relatório JSON.
