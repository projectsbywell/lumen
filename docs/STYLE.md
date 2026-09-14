# Guia de estilo Lumen v0.1

> Convenções oficiais de formatação e nomenclatura. O formatador
> (`lumen fmt`) aplica estas regras automaticamente.

## 1. Princípios

1. **Legibilidade primeiro** — código Lumen é lido mais do que escrito.
2. **`lumen fmt` decide** — em caso de dúvida, rode o formatador.
3. **Explícito em fronteiras, inferido no miolo** — assinaturas públicas
   sempre anotadas; variáveis locais usam inferência.

## 2. Formatação

| Regra | Certo | Errado |
|---|---|---|
| Indentação 4 espaços | `····let x = 1;` | tabs |
| Chave de abertura na mesma linha | `fn f() {` | `fn f()\n{` |
| Ponto-e-vírgula obrigatório | `let x = 1;` | `let x = 1` |
| Espaços ao redor de `=`, `+`, `->`, `=>` | `a -> i32`, `1 => x` | `a->i32`, `1=>x` |
| Sem espaço em `::`, `!`, `?` | `io::println(x); r?;` | `io :: println` |
| Linha ≤ 100 colunas | — | linhas longas |
| Arquivo termina com `\n` | — | sem newline |
| String com `"` duplas | `"texto"` | `'texto'` (char!) |

```lum
/// Soma dois inteiros.
pub fn soma(a: i32, b: i32) -> i32 {
    return a + b;
}

fn main() {
    let total = soma(2, 3);
    match total {
        0 => io::println("zero"),
        1 | 2 => io::println("pequeno"),
        n if n > 10 => io::println("grande"),
        _ => io::println("outro"),
    }
}
```

## 3. Nomenclatura

| Elemento | Convenção | Exemplo |
|---|---|---|
| Função, variável, parâmetro, módulo | `snake_case` | `ler_arquivo`, `total` |
| Tipo, struct, enum, trait | `PascalCase` | `Ponto`, `Resposta` |
| Variante de enum | `PascalCase` | `Cor::Vermelho` |
| Constante | `SCREAMING_SNAKE` | `MAX_TENTATIVAS` |
| Macro (definição e chamada) | `snake_case` + `!` no uso | `unless!(cond) { }` |
| Arquivo `.lum` | `snake_case` | `minha_lib.lum` |
| Teste | `testa_<o_que>` | `testa_soma` |

- Tipos genéricos: uma letra (`T`, `E`, `K`, `V`).
- Bool: prefixo `eh_`, `tem_`, `pode_` (`eh_valido`, `tem_chave`).
- Evite abreviações (`indice`, não `idx`; `resposta`, não `resp`).

## 4. Tipos e assinaturas

- **Toda `pub fn` tem tipos de parâmetros e retorno anotados.**
- Prefira `str` (empréstimo) em parâmetros e `String` só quando a função
  precisa tomar posse: `fn saudacao(nome: str) -> String`.
- Erro recuperável → `Result<T, E>` + `?`; valor ausente → `Option<T>`.
  `panic("...")` é só para invariante quebrada (bug), nunca para erro de IO.
- `String` coage para `str` onde `str` é esperado (`println` aceita ambos);
  `+` vale para qualquer combinação de `str`/`String` e devolve `String`.
- `mut` só onde há escrita: `fn push(v: mut Vec<T>, x: T)`.

## 5. Structs, enums e `match`

```lum
/// Ponto no plano.
pub struct Ponto { x: f64, y: f64 }

/// Resultado de uma operação que pode falhar.
pub enum Resultado { Ok(i32), Erro(str) }

fn descreve(r: Resultado) -> str {
    return match r {
        Resultado::Ok(0) => "zero",
        Resultado::Ok(n) => "valor",
        Resultado::Erro(msg) => msg,
    };
}
```

- Um variante por linha em enums com payload.
- `match` deve ser **exaustivo**: termine com `_` ou cubra todos os casos.
- Guards (`n if n > 0`) depois do padrão, antes do `=>`.
- `if/else` para 2 ramos booleanos; `match` para 3+ ramos ou destruturação.

## 6. Comentários e docs (`///`)

- `//` explica **porquê**, nunca repete o **quê**.
- `///` em **todo item `pub`** (função, struct, enum, módulo, const):
  1ª linha = resumo; parágrafo seguinte = detalhes/exemplo.
- Exemplo mínimo em `///` para cada função pública da stdlib.

```lum
/// Fatorial de `n` (`n!`).
///
/// Retorna `Err` se `n < 0`.
pub fn fat(n: i32) -> Result<i32, str> { }
```

## 7. Erros — o operador `?`

```lum
use std::fs;

fn carrega(caminho: str) -> Result<String, str> {
    let texto = fs::read_arquivo(caminho)?;  // propaga Err
    return Ok(texto);
}
```

- Não ignore `Result`: ou `?`, ou `match`, ou `unwrap_or`.
- Mensagens de `Err(str)` em minúsculas, sem ponto final: `"arquivo vazio"`.

## 8. Testes e macros

```lum
#[test]
fn testa_fat() {
    assert_eq(math::fat(5), Ok(120));
}

/// Executa o bloco só se `cond` for falsa.
macro unless(cond, corpo) {
    if !cond { corpo }
}
```

- Um `#[test]` por comportamento; nome `testa_<comportamento>`.
- Macros: nomes curtos, documente a expansão com exemplo.

## 9. `async`/`await`

```lum
async fn buscar(url: str) -> str { }

fn main() {
    let h = spawn buscar("https://exemplo.com");
    let corpo = await h;
    io::println(corpo);
}
```

- `async fn` para IO que espera; código CPU-bound continua síncrono.
- `spawn` retorna `Handle<T>`; `await` consome o handle uma vez.

## 10. Imports e layout de arquivo

```lum
/// Uma linha: o que o módulo faz.
use std::io;
use std::math;

const VERSAO: str = "0.1.0";

pub struct Ponto { x: f64, y: f64 }

pub fn novo(x: f64, y: f64) -> Ponto { }

fn main() { }
```

Ordem: doc do módulo → `use` → `const` → tipos → `impl` → funções →
`main` → `#[test]`. Um tipo principal por arquivo.
