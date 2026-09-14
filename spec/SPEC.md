# Lumen — Especificação da Linguagem

**Versão:** 0.5.4 (2026-09-14)  
**Autores:** Lumen Lang Team  
**Status:** Draft Normativo  
**Licença:** MIT / Apache-2.0

---

## 1. Propósito e Escopo

Lumen é uma linguagem de sistemas **pragmática, segura e concorrente**, desenhada para:

- **Substituir glue code** (Python/JS) com performance nativa, sem sacrificar ergonomia.
- **Competir com Rust/Go** em serviços e WASM, com curva de aprendizado menor.
- **Alvo múltiplo:** nativo (via C), WebAssembly, e VM interpretada para REPL/testes.

Princípios norteadores:

1. **Legibilidade primeiro:** `let mut y = x + 1` funciona sem anotação; tipos aparecem onde ajudam.
2. **Nominal onde importa, estrutural onde convém:** domínio usa `struct` nominal; dados ad-hoc usam `{x: float, y: float}`.
3. **Ownership sem dor:** borrow checker com elisão agressiva; 80% do código nunca escreve `&` explícito (passagem por valor com move/copy).
4. **Async como cidadão de primeira classe:** `async/await` builtin, não biblioteca.
5. **Tooling é feature:** `lumen test`, `lumen fmt`, `lumen pkg` inclusos.

Este documento-mãe consolida as 3 especificações normativas:

| Documento | Conteúdo | Normatividade |
|-----------|----------|---------------|
| [`EBNF.md`](./EBNF.md) | Gramática léxica e sintática completa | Normativa |
| [`TIPOS.md`](./TIPOS.md) | Sistema de tipos (nominal+estrutural, inferência, subtipagem, genéricos, traits) | Normativa |
| [`SEMANTICA.md`](./SEMANTICA.md) | Semântica operacional small-step + denotacional + ownership/borrow + async | Normativa |

Em caso de conflito, a ordem de precedência é: `SEMANTICA.md` > `TIPOS.md` > `EBNF.md` para comportamento de execução; `EBNF.md` prevalece para o que é programa válido.

ADRs (decisões arquiteturais) estão em `ADR-001` … `ADR-005` e justificam escolhas não óbvias.

---

## 2. Visão de 30 Segundos

```lumen
module hello
import std.io

pub fn main() -> int {
    io.println("olá");
    return 0;
}
```

```lumen
let x: int = 42;
let mut y = x + 1
if x > 0 { y += 1; } else { y -= 1; };
match v { 0 => "zero", _ => "outro" }

struct Ponto { x: float, y: float }
enum Opt<T> { Nenhum, Algum(T) }

trait Mostrar { fn mostra(self) -> string; }
impl Mostrar for Ponto {
    fn mostra(self) -> string { return "Ponto(\(self.x), \(self.y))"; }
}

async fn carregar(url: string) -> string {
    let r = std.http.get(url).await;
    return r.text().await;
}

#[test]
fn test_ponto() { assert(Ponto{x:1.0,y:2.0}.x == 1.0); }
```

Compilação:

```bash
lumen build --target native    # via backend C
lumen build --target wasm
lumen test                     # descobre #[test]
lumen run hello.lm
```

---

## 3. Arquitetura do Documento

```
SPEC.md (você está aqui)
 ├─ EBNF.md        → O que é texto válido
 ├─ TIPOS.md       → O que é programa bem tipado
 ├─ SEMANTICA.md   → O que o programa faz
 └─ ADR-*.md       → Por que foi assim
```

Leitura recomendada:

1. Engenheiro de linguagem: `EBNF` → `TIPOS` → `SEMANTICA`
2. Usuário: este `SPEC` §7 (exemplos) + `EBNF` §12
3. Implementador de backend: `SEMANTICA` §2-4 + `ADR-004`

---

## 4. Decisões de Design Justificadas

### D1. Sintaxe com `module`/`import` e `pub fn` explícito

**Escolha:** `module hello` no topo, `import std.io`, `pub fn main() -> int`.

**Alternativas rejeitadas:** `package`/`use` (Go/Rust), `export` implícito, `fn main()` sem tipo de retorno.

**Justificativa:** `module` singular e `import` espelham o filesystem (`hello.lm` → `module hello`); `pub` por padrão privado evita vazamento de API (erro comum em Python/JS). Retorno `-> int` explícito torna `main` tratável como função normal e permite `return` com código de saída em `native`/`wasm`.

### D2. `let` / `let mut` em vez de `var`/`val`

**Escolha:** imutável por padrão, `mut` opt-in.

**Justificativa:** alinha com ownership: `let x = ...` cria `Own immutável`; `let mut y` cria `Own mutável` que pode ser emprestado `&mut`. Evita classe de bugs de reatribuição acidental, sem verbosidade de `const`/`let` de JS. Inferência cobre `y` sem anotação (`y: int` deduzido de `x + 1`).

### D3. Nominal + Estrutural híbrido

**Escolha:** `struct Ponto` nominal; `{x: float, y: float}` estrutural anônimo.

**Justificativa:** nominal protege invariantes de domínio ( `Ponto` ≠ `Vetor` mesmo com mesmos campos, evita confusão de unidades). Estrutural dá ergonomia para JSON-like, interoperabilidade com `std.json`, e prototipação rápida sem declarar `struct` para cada forma. Subtipagem por largura em records (`{x,y,z} <: {x,y}`) permite funções genéricas sobre shapes.

### D4. Inferência bidirecional, não global

**Escolha:** HM restrito a `let`, assinaturas `fn` exigem tipos (exceto `fn` privada pode inferir).

**Justificativa:** inferência global (como em ML) quebra diagnostics e tempo de compilação em bases grandes; bidirecional dá erro local preciso ("esperado `int`, encontrado `string` na linha 3"). `let mut y = x + 1` sem anotação cobre 90% dos casos locais.

### D5. Traits como bounds, não herança

**Escolha:** `trait Mostrar { fn mostra(self)->string; }` + `impl Mostrar for Ponto`.

**Justificativa:** evita hierarquia de classes; composição supera herança. Traits dão polimorfismo ad-hoc com coerência (orphan rule) sem custo de vtables quando monomorfizado. `T: Add + Copy` é mais expressivo que `extends` e permite retroactive modeling (implementar trait para tipo de terceiro se em mesmo crate).

### D6. Ownership simplificado com elisão

**Escolha:** move por padrão para `!Copy`, `Copy` para primitivos; `&`/`&mut` só quando precisa emprestar; lifetimes elididos.

**Justificativa:** Rust expõe lifetimes cedo e assusta iniciantes. Lumen mira em "ownership invisível" para 80% do código (pass by value com move elidido via NRVO). Borrow checker só aparece quando `&` é escrito. Semântica `Moved` e `BorrowImm(n)` em `SEMANTICA.md` é idêntica a Rust, mas surface syntax esconde `'`a na maioria das funções.

### D7. `async`/`await` builtin, não library

**Escolha:** `async fn` desugars para `Future`, `await` é keyword pós-fixa.

**Justificativa:** concorrência é requisito desde dia 0 (serviços, fetch WASM). Se `async` fosse biblioteca, ergonomia de `?` e `for await` sofreria. Desugar para `Future` trait mantém backend simples (poll loop). Targets `native` (epoll) e `wasm` (Promise) compartilham mesma semântica.

### D8. Macros higiênicas `macro` + `!`

**Escolha:** `macro vec_of { ... }` e invocação `vec_of![1,2,3]`, `println!("olá")`.

**Justificativa:** macros são necessárias para `println!`, `vec!`, `assert!` sem varargs runtime. Higiene evita captura acidental. Fase de expansão antes de resolução de nomes mantém parser simples. `!` visual distingue expansão compile-time de chamada runtime.

### D9. Anotações de teste `#[test]` / `#[bench]`

**Escolha:** atributo sobre `fn`, descoberto por `lumen test`.

**Justificativa:** testes co-localizados com código aumentam cobertura; `#[test]` é padrão de Rust familiar. Runner injeta harness que coleta `#[test]` via reflexão em `vm` e via monomorfização em `native`. `#[should_panic]` e `#[bench]` seguem mesma sintaxe.

### D10. `match` exaustivo com `_`

**Escolha:** `match v { 0 => "zero", _ => "outro" }` exige exaustividade; `_` é wildcard.

**Justificativa:** exaustividade previne bugs de `switch` não tratado. `_` explícito documenta intenção; checker emite erro se variante de `enum` não coberta. `match` é expressão (retorna valor), permitindo `let s = match v { ... }`.

### D11. Backends múltiplos com semântica única

**Escolha:** `c` (nativo), `wasm`, `vm` (interpretado) com mesma `SEMANTICA.md`.

**Justificativa:** `vm` para REPL e testes rápidos; `wasm` para frontend; `c` para distribuição nativa sem LLVM. Semântica única garante que `lumen test` (vm) e `lumen build --target native` observam mesmo comportamento (exceto overflow wrap vs panic, documentado).

---

## 5. Semântica Resumida (normativa por referência)

- **Valores e estado:** ver `SEMANTICA.md` §1.
- **Small-step:** `⟨e, σ⟩ → ⟨e', σ'⟩` com contextos `E`, regras para `let`, `borrow`, `call`, `match`, `for` (desugar), `async/await`, `?`/`panic`.
- **Ownership:** `Own → Moved` em move, `BorrowImm(n)` / `BorrowMut` com borrow checker estático sound.
- **Denotação:** `⟦e⟧ : Env → Store → (D × Store)` composicional; adequação com small-step provada por indução.

Detalhes completos em `SEMANTICA.md`.

---

## 6. Sistema de Tipos Resumido

- **Nominais:** `struct`/`enum` criam identidade única; `Ponto` ≮ `Vetor`.
- **Estruturais:** `{x: float, y: float}`, `(T,U)`, `fn(T)->U` comparados por estrutura.
- **Subtipagem:** largura para records, covariância para imutáveis, contravariância para `fn` params, `! <: τ`.
- **Genéricos:** `fn id<T: Clone>(x: T)->T`, `where` clauses, tipos associados `I::Item`.
- **Traits:** bounds `T: Mostrar + Clone`, impl coerence (orphan rule), resolução por unificação.

Ver `TIPOS.md` para julgamentos `Γ ⊢ e : τ` e regras completas.

---

## 7. Exemplos de Código Lumen (normativos)

### 7.1 Hello World

```lumen
module hello
import std.io

pub fn main() -> int {
    io.println("olá");
    return 0;
}
```

### 7.2 Struct, Enum, Match, If

```lumen
module exemplo
import std.io

struct Ponto { x: float, y: float }
enum Opt<T> { Nenhum, Algum(T) }

fn descreve(v: int) -> string {
    return match v {
        0 => "zero",
        1 => "um",
        _ => "outro"
    };
}

pub fn main() -> int {
    let x: int = 42;
    let mut y = x + 1;
    if x > 0 { y += 1; } else { y -= 1; }
    let p = Ponto { x: 1.0, y: 2.0 };
    let o: Opt<int> = Opt::Algum(y);
    let s = match o {
        Opt::Nenhum => "vazio",
        Opt::Algum(v) => descreve(v)
    };
    io.println(s);
    return 0;
}
```

### 7.3 Genéricos e Traits

```lumen
module generics

trait Area { fn area(self) -> float; }

struct Retangulo { largura: float, altura: float }
impl Area for Retangulo {
    fn area(self) -> float { return self.largura * self.altura; }
}

fn maior_area<T: Area + Clone>(a: T, b: T) -> T {
    if a.area() > b.area() { return a; } else { return b; }
}

fn id<T>(x: T) -> T { return x; }
let a = id<int>(42);
let b = id("olá"); // inferido string
```

### 7.4 Ownership e Borrow

```lumen
module ownership

fn consuma(s: string) { /* move */ }

pub fn main() -> int {
    let s: string = "olá";
    let t = s;           // move: s fica Moved
    // consuma(s)        // ERRO: uso após move

    let mut p = Ponto { x: 1.0, y: 2.0 };
    let r: &Ponto = &p;  // borrow imut
    // p.x = 3.0         // ERRO: mut enquanto emprestado
    let x = r.x;         // OK: leitura via borrow
    // fim de r, borrow expira
    p.x = 3.0;           // OK agora
    return 0;
}
```

### 7.5 Async

```lumen
module async_demo
import std.http
import std.io

async fn buscar(url: string) -> string {
    let resp = http.get(url).await;
    let texto = resp.text().await;
    return texto;
}

pub async fn main() -> int {
    let a = buscar("https://example.com").await;
    io.println(a);
    return 0;
}
```

### 7.6 Macros

```lumen
module macros
import std.io

macro vec_of(expr: expr) => { std.vec.Vec::from([expr]) }

pub fn main() -> int {
    let v = vec_of![1, 2, 3];
    println!("tamanho \(v.len())");
    return 0;
}
```

### 7.7 Testes

```lumen
module mymath

pub fn soma(a: int, b: int) -> int { return a + b; }

#[test]
fn test_soma_basico() {
    assert(soma(2,2) == 4);
}

#[test(should_panic)]
fn test_panic_esperado() {
    panic("ops");
}

#[bench]
fn bench_soma() {
    for i in 0..10000 { soma(i, i); }
}
```

### 7.8 Tipo Estrutural

```lumen
module structural

fn norma(p: {x: float, y: float}) -> float {
    return p.x * p.x + p.y * p.y;
}

pub fn main() -> int {
    let a = {x: 1.0, y: 2.0};              // record anônimo
    let b = {x: 1.0, y: 2.0, z: 3.0};       // subtipo por largura
    let n1 = norma(a); // OK
    let n2 = norma(b); // OK: {x,y,z} <: {x,y}
    let p = Ponto { x: 1.0, y: 2.0 };
    // norma(p) // ERRO: Ponto nominal ≠ record, precisa: norma(p as {x:float,y:float})
    return 0;
}
```

---

## 8. Toolchain e Targets

- `lumen build --target native` → C (via `compiler/backend/c`) → `cc`/`clang`
- `lumen build --target wasm` → WASM (via `compiler/backend/wasm`) → `wasm32`
- `lumen run` / `lumen test` → VM (via `compiler/backend/vm`) interpretado

Todos compartilham `frontend` (lexer/parser → AST → HIR) e `middle` (typeck, borrowck, monomorfização).

Versionamento: SemVer `0.5.4`, ver `ADR-005`.

> **Nota de honestidade (revisão v0.5.4):** a suíte de conformidade
> `conformance/suite.py` (50/50) é um **subset da v0.1** — cobre lexer,
> parser, tipos, `match`, struct/enum, bytecode, backends, runtime e
> stdlib no nível expresso nos casos, mas **não cobre macroscopicamente
> GC, `async`/concorrência nem traits** (sem casos de pressão de heap,
> escalonamento, `await` ponta-a-ponta ou verificação de bounds em
> call-sites). Ver itens 5/9 dos revisores em `LIMITACOES.md`.

---

## 9. Conformidade

Um compilador é conforme se:

1. Aceita exatamente programas deriváveis de `Programa` em `EBNF.md`.
2. Rejeita programas mal tipados segundo `TIPOS.md` (com diagnostics compatíveis).
3. Executa programas bem tipados com observáveis idênticos a `SEMANTICA.md` (small-step).
4. `lumen test` descobre todas as `#[test]` e `#[bench]` conforme `EBNF.md` §11.

Testes de conformidade em `conformance/`.

---

## 10. Referências

- `EBNF.md` — Gramática
- `TIPOS.md` — Tipos
- `SEMANTICA.md` — Semântica
- `ADR-001` — Sintaxe
- `ADR-002` — Tipos
- `ADR-003` — Ownership
- `ADR-004` — Targets
- `ADR-005` — Versionamento

---

*Fim de SPEC.md*
