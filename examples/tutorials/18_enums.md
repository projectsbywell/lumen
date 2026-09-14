# 18 — Enums modelam estados

Se o valor só pode ser uma de N coisas, é `enum` (006, 043, 047):

```lum
enum Estado { Novo, Pagamento, Enviado, Cancelado }
enum Acao { Pagar, Enviar, Cancelar }

fn transicao(e: Estado, a: Acao) -> Estado {
    return match e {
        Estado::Novo => match a {
            Acao::Pagar => Estado::Pagamento,
            Acao::Cancelar => Estado::Cancelado,
            _ => e,
        },
        _ => e,
    };
}
```

O compilador cobra exaustividade (cobrir todos os casos): esqueceu um
braço, o `match` reclama. Assim, um estado inválido (ex.: "enviado sem
pagar") nem tem como ser escrito — o `match` obriga a tratar cada caso.

## Exercícios

1. Adicione `Estado::Reembolso` e veja onde o compilador aponta.
2. Semáforo (verde→amarelo→vermelho) como enum + `proximo()`.
3. `Papel { Admin, Editor, Leitor }` com permissões por variante (047).
