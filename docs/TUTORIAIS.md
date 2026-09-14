# Tutoriais Lumen — do zero ao avançado

> Roteiro progressivo. Cada nível tem exemplos rodáveis em `examples/`
> e um tutorial guiado em `examples/tutorials/`. Tempo estimado total: ~20h.

| Nível | Tema | Exemplos | Tutorial | Tempo |
|---|---|---|---|---|
| 0 | Instalação + Hello | `001_hello` | `01_hello.md` | 20 min |
| 1 | Funções, tipos, controle | `002_fatorial`, `003_fibonacci`, `010_math` | `02_funcoes_tipos.md` | 45 min |
| 2 | Struct, enum, `match` | `004_match`, `005_struct`, `006_enum` | `03_struct_enum_match.md` | 1h |
| 3 | Coleções, strings, IO | `007_colecoes`, `008_strings`, `009_io` | `04_colecoes_strings_io.md` | 1h |
| 4 | Projeto: HTTP + SQLite + testes + macro + async | `011_http`–`016_cli_json` | `05_projeto.md` | 2h30 |
| 5 | Algoritmos básicos | `017_bubble_sort`, `018_busca_binaria` | `06_algoritmos.md` | 1h |
| 6 | Estruturas de dados | `019_pilha`–`021_tabela_hash`, `039_paginacao` | `07_estruturas.md` | 1h30 |
| 7 | Recursão | `002_fatorial`, `023_arvore`, `024_grafo_bfs` | `08_recursao.md` | 1h |
| 8 | Complexidade | `025_memoizacao`, `033_fib_memo` | `09_complexidade.md` | 45 min |
| 9 | Strings | `008_strings`, `026_palindromo`–`029_csv` | `10_strings.md` | 1h |
| 10 | Matemática | `010_math`, `031_calculadora`–`034_estatistica` | `11_math.md` | 1h |
| 11 | IO e arquivos | `009_io`, `029_csv`, `036_log` | `12_io.md` | 45 min |
| 12 | CLI | `016_cli_json`, `035_config` | `13_cli.md` | 45 min |
| 13 | Projeto completo | `045_pedido`, `046_carrinho` | `14_projeto.md` | 2h |
| 14 | Async | `015_async`, `042_tarefas_async` | `15_async.md` | 1h |
| 15 | Testes | `013_teste`, `040_validador` | `16_testes.md` | 45 min |
| 16 | Match avançado | `004_match`, `043_maquina_estado` | `17_match_avancado.md` | 45 min |
| 17 | Enums e estados | `006_enum`, `047_auth` | `18_enums.md` | 45 min |
| 18 | Erros como valores | `002_fatorial`, `038_retry`, `048_pipeline` | `19_erros.md` | 1h |
| 19 | Publicação | registry + `lumen_pkg` | `20_publicacao.md` | 30 min |
| v0.3 | Macros higiênicas, keywords novas, async/GC | `051_macro_higienica`–`054_registros_traits` | `15_async.md` | 1h |

---

## Nível 0 — Hello, Lumen

```lum
/// Meu primeiro programa.
fn main() {
    println("Olá, Lumen!");
}
```

```sh
python3 compiler/run.py examples/001_hello.lum
# → Olá, Lumen!
```

Conceitos: `fn main` é a porta de entrada; `println` imprime com `\n`;
toda instrução termina com `;`. Detalhes em `examples/tutorials/01_hello.md`.

## Nível 1 — Funções, tipos e controle

```lum
use std::math;

/// Fatorial recursivo.
fn fat(n: i32) -> Result<i32, str> {
    if n < 0 {
        return Err("n negativo");
    }
    if n <= 1 {
        return Ok(1);
    }
    let sub = fat(n - 1)?;          // `?` propaga o Err
    return Ok(n * sub);
}

fn main() {
    match fat(5) {
        Ok(v) => println("5! = " + v),
        Err(e) => println("erro: " + e),
    }
    for i in 0..5 { println(i); }    // 0 1 2 3 4
}
```

Conceitos: tipos (`i32`, `f64`, `bool`, `str`), `let`/`mut`, `if/else`,
`for in 0..n`, `while`, `Result` + `?`, `match` básico.
Ver `02_funcoes_tipos.md` e `examples/002_fatorial.lum`.

## Nível 2 — Struct, enum e `match`

```lum
/// Forma geométrica.
enum Forma {
    Circulo(f64),
    Retangulo(f64, f64),
    Ponto,
}

fn area(f: Forma) -> f64 {
    return match f {
        Forma::Circulo(r) => 3.14159 * r * r,
        Forma::Retangulo(w, h) => w * h,
        Forma::Ponto => 0.0,
    };
}
```

Conceitos: `struct` + `impl`, enums com payload, destruturação,
padrões `|` e guards (`n if n > 0`), exaustividade (`_`).
Ver `03_struct_enum_match.md`.

## Nível 3 — Coleções, strings e IO

```lum
use std::io;

fn main() {
    let mut nomes = vec!["ana", "bia"];
    vec::push(nomes, "cid");
    let texto = str::join(nomes, ", ");
    println(texto);

    let linha = io::read_line()?;
    println(str::upper(linha));
}
```

Conceitos: `vec![...]`, `map!{...}`, `Vec::map/filter`, `Map`,
`str::split/join/trim`, `fs::read_arquivo/write_arquivo`.
Ver `04_colecoes_strings_io.md`.

## Nível 4 — Projeto guiado (HTTP + SQLite + async + macro + testes)

Você monta um mini-agregador: baixa JSON via `http::get`, salva em
SQLite, expõe consulta `async` e cobre tudo com `#[test]`:

```lum
use std::http;
use std::sqlite;

macro garante_ok(res, msg) {
    match res {
        Ok(v) => v,
        Err(e) => panic(msg + ": " + e),
    }
}

async fn sincroniza(db: mut sqlite::Db, url: str) -> i32 {
    let r = garante_ok!(http::get(url), "falha http");
    return garante_ok!(sqlite::exec(db, r.corpo), "falha sql");
}

#[test]
fn testa_sincroniza() {
    let mut db = garante_ok!(sqlite::abrir(":memory:"), "abrir");
    assert_eq(sincroniza(db, "https://api.exemplo.com/itens"), 3);
}
```

Ver `05_projeto.md` (passo a passo completo, ~2h30).

---

## Nível v0.3 — Macros higiênicas, keywords novas, async e GC automático

### Macros higiênicas (não-captura por shadowing)

A macro `soma_um!` possui binding local `n` que é **gensym'd** para `__hygN`.
A `n` do escopo do chamador não é capturada nem movida: a expansão usa
`__hyg1` como nome interno, garantindo isolamento total.

```lum
/// Macro que soma 1 ao argumento. O binding `n` é gensym'd para não capturar.
macro soma_um(x) {
    let n = x + 1;
    return n;
}

fn main() {
    let n = 10;
    let resultado = soma_um!(n);
    println(resultado);
    println(n);
}
```

### Keywords reais, raw identifiers, atributos com args, literais com sufixo

A v0.3 promove `self`/`Self`/`type`/`super`/`crate` a keywords reais,
adiciona `r#nome` para raw identifiers, `#[test(args)]` com args,
literais com sufixo (`42i32`, `3.0f64`), `r#"..."#` (raw strings),
`\u{...}` (unicode escapes) e `/* aninhados */` (comentários aninhados).

```lum
/// Raw identifier como nome de campo.
struct r#type {
    r#value: i32,
}

/// Literais com sufixo e raw strings.
fn main() {
    let a = 42i32;
    let b = 3.14f64;
    let msg = r#"Valor: \u{1F600}"#;
    let t = r#type { r#value: 7i32 };
}
```

### Async/await e limitação do Channel

`spawn` agenda tarefas cooperativas; `await` consome o resultado.
O runtime (`runtime/threads.py`) provê `Future`, `poll`, `block_on`
e `Channel.receber(timeout=0)` para recepção não-bloqueante.

**Atenção:** `channel`/`Channel` NÃO está disponível via `.lum`
(sem `use std::sync::channel` na stdlib). Para usar Channel,
acesso direto ao `runtime/threads.py` via Python.

```lum
async fn soma_intervalo(inicio: i32, fim: i32) -> i32 {
    let mut total = 0i32;
    let mut i = inicio;
    while i < fim {
        total = total + i;
        i = i + 1;
    }
    return total;
}

async fn soma_concorrente() -> i32 {
    let ha = spawn soma_intervalo(0, 1000);
    let hb = spawn soma_intervalo(1000, 2000);
    return await ha + await hb;
}

fn main() {
    let h = spawn soma_concorrente();
    println(str::from_int(await h));
}
```

### GC automático (roots automáticos)

O coletor `runtime/gc.py` registra roots automaticamente via
`registrar_frame`/`remover_frame` (frames da VM) e
`definir_global`/`remover_global` (globals). `marcar_root`/
`desmarcar_root` permanecem como override manual.

```lum
/// O GC rastreia frames e globals automaticamente.
/// `marcar_root` é o override manual para objetos de longa duração.
fn main() {
    let dados = vec![1, 2, 3];
    // O frame e as locals são roots automáticos.
    // O GC promove objetos da nursery para old quando necessário.
}
```

Ver `examples/051_macro_higienica.lum`, `examples/052_keywords_records.lum`,
`examples/053_async_spawn.lum`, `examples/054_registros_traits.lum`.

---

## Para onde ir depois

- `docs/API.md` — referência de toda a stdlib.
- `docs/STYLE.md` — escreva como um nativo.
- `examples/book/LIVRO.md` — o livro, capítulos 0→avançado.
- `conformance/suite.py` — veja cada feature virar caso executável.
