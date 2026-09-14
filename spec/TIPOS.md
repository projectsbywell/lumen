# Lumen — Sistema de Tipos

**Versão:** 0.5.4  
**Status:** Normativo — complementa `EBNF.md` e `SEMANTICA.md`  
**Referência-mãe:** `SPEC.md` §4

---

## 1. Visão Geral

Lumen adota sistema **híbrido nominal + estrutural** com inferência bidirecional, subtipagem por largura/profundidade e polimorfismo paramétrico com traits como bounds.

Objetivos:
- Ergonomia de scripting (`let mut y = x + 1` sem anotação) + rigor de sistemas.
- Nominal para entidades de domínio (`struct Ponto` ≠ `struct Vetor` mesmo com mesmos campos).
- Estrutural para dados anônimos, interoperabilidade e inferência local (`{x: float, y: float}`).
- Segurança de ownership sem GC obrigatório, via borrow checker elidido.

```
Nominal  ── struct/enum/trait impl  (identidade por nome + crate)
Estrutural ── tupla, fn, record anônimo {x: T, y: U}, array/slice
```

Kinds: `Type`, `Lifetime` (elidido por padrão), `Const` (para `N` em `[T; N]`).

---

## 2. Sintaxe de Tipos (resumo tipado)

Reuso de `EBNF.md` §5. Aqui a forma internalizada:

```
τ ::= int | i32 | i64 | ... | float | f64 | bool | char | string | str | !
    | τ -> τ                          (* função, ex: fn(int) -> string *)
    | (τ, ..., τ)                     (* tupla, () é unit *)
    | [τ; n] | [τ]                    (* array fixo, slice *)
    | &μ τ | *μ τ                     (* referência, ponteiro; μ = mut|const *)
    | C<τ...>                         (* nominal: C é struct/enum/trait *)
    | { l: τ, ... }                   (* record estrutural *)
    | α                               (* variável de tipo *)
    | _                               (* inferência *)
μ ::= mut | imm
```

Contextos:

- `Γ` — ambiente de tipos: `x: τ, T: Trait, ...`
- `Σ` — tabela de definições nominais (struct/enum/trait/impl)

Julgamentos:

- `Σ; Γ ⊢ e : τ` — expressão `e` tem tipo `τ`
- `Σ; Γ ⊢ τ <: σ` — subtipagem
- `Σ ⊢ τ wf` — tipo bem formado
- `Σ; Γ ⊢ p : τ ⊣ Γ'` — pattern `p` casa `τ` e estende `Γ'`

---

## 3. Tipos Nominais

### 3.1 Definição e identidade

Cada `struct`/`enum` define um novo tipo nominal único:

```lumen
struct Ponto { x: float, y: float }
struct Vetor { x: float, y: float }

let p: Ponto = Ponto { x: 1.0, y: 2.0 };
let v: Vetor = Vetor { x: 1.0, y: 2.0 };
// p = v  // ERRO: Ponto ≠ Vetor (nominal), mesmo com estrutura idêntica
```

Regra:

```
Σ contém  struct C<α... where ...> { f: τ ... }
─────────────────────────────────────────────── (Nominal-WF)
Σ ⊢ C<σ...> wf   se  Σ; α↦σ ⊢ τ[α↦σ] wf  e bounds satisfeitos
```

Compatibilidade nominal só via coerção explícita ou trait comum, nunca por estrutura.

### 3.2 Enums nominais com payload

```lumen
enum Opt<T> { Nenhum, Algum(T) }
enum Resultado<T, E> { Ok(T), Erro(E) }

let o: Opt<int> = Opt::Algum(42);
match o { Opt::Nenhum => 0, Opt::Algum(v) => v }
```

Cada variante é construtor injetor `C::V : τ_payload -> C<...>`.

### 3.3 Type aliases — transparência

`type Alias<T> = Vec<T>` é transparente: `Alias<int>` ≡ `Vec<int>` para todos os julgamentos, mas preserva nome para diagnostics.

---

## 4. Tipos Estruturais

### 4.1 Records anônimos

```
{ x: float, y: float }   : Type
```

Tipagem estrutural pura:

```lumen
fn len(p: {x: float, y: float}) -> float { return p.x + p.y; }

let a: {x: float, y: float} = {x: 1.0, y: 2.0};
let b: Ponto = Ponto { x: 1.0, y: 2.0 };
// len(b)  // ERRO? Veja §6 subtipagem: Ponto NÃO é subtipo de record,
// mas coercion automática via `as` estrutural: len(b as {x:float,y:float}) OK
// Porém match estrutural aceita subtyping por largura (§6.1)
let c = {x: 1.0, y: 2.0, z: 3.0};
len(c) // OK por subtipagem largura: {x,y,z} <: {x,y}
```

Regra estrutural:

```
Σ; Γ ⊢ e1: τ1  ...  en: τn
─────────────────────────────────
Σ; Γ ⊢ { l1: e1, ..., ln: en } : { l1: τ1, ..., ln: τn }
```

Ordem de campos irrelevante para subtipagem, mas relevante para construção.

### 4.2 Tuplas, funções e arrays

- Tuplas: `(int, string)` é estrutural; `(int, string) <: (int, _)` não, mas coerção para `(_)` via `_`.
- Funções `fn(A)->B` são estruturais: compatibilidade por contravariância no parâmetro.
- Arrays `[T; N]` e slices `[T]`: `*[T; N]` coage para `&[T]`.

---

## 5. Inferência de Tipos

### 5.1 Estratégia: Bidirecional + Hindley-Milner restrito

Lumen não exige anotações em `let` local; exige em assinatura `fn` pública (exceto `pub fn` com corpo inferido internamente mas exposto com tipo concreto no .lmi).

Modos:

- **Síntese** `Γ ⊢ e ⇒ τ` (inferir)
- **Checagem** `Γ ⊢ e ⇐ τ` (verificar contra esperado)

```
Γ ⊢ e ⇒ τ    τ <: σ
──────────────────── (Sub)
Γ ⊢ e ⇐ σ

Γ ⊢ 42 ⇒ int
Γ ⊢ x ⇒ Γ(x)
Γ, x: α ⊢ e ⇒ τ
────────────────────────────── (Let-Infer)
Γ ⊢ let x = e1; e2  ⇒  ...
```

Algoritmo W adaptado com:

- Generalização apenas em `let` (let-polymorphism), não em lambdas.
- `let mut y = x + 1` → `y: int` inferido do `+` (Add<int,int>::Output = int).
- `_` como tipo hole: `let x: _ = 42` sintetiza `int` e unifica.

### 5.2 Exemplo de inferência

```lumen
let x: int = 42;        // checagem: 42 ⇐ int ✓
let mut y = x + 1       // síntese: x:int, 1:int => + : (int,int)->int => y:int
let id = |x| x          // síntese: α -> α  (generaliza se let)
let a = id(42)          // instância: α=int => a:int
let b = id("olá")       // re-instância: α=string => b:string  (id é polimórfico por let)
```

Erro de inferência reporta com expected vs found + sugestão `as`.

### 5.3 Inferência de lifetimes

Lifetimes são elididos: `fn foo(s: &string) -> &string` → `fn foo<'a>(s: &'a string) -> &'a string` por elisão (um input lifetime → output herda). Múltiplos inputs exigem anotação explícita (futuro, hoje erro).

---

## 6. Subtipagem

Relação `τ <: σ` (τ subtipo de σ). Reflexiva, transitiva, decidível.

### 6.1 Regras estruturais

**Largura para records:**

```
{ l1: τ1, ..., ln: τn, ... } <: { l1: τ1, ..., ln: τn }
────────────────────────────────────────────────────────── (Width)
Ex: {x: float, y: float, z: float} <: {x: float, y: float}
```

**Profundidade (covariante em campos imutáveis):**

```
τi <: σi  para todo i
─────────────────────────────────
{ l: τ } <: { l: σ }   se campos são imutáveis (sem mut)
```

Se campo é `mut`, invariante: `&mut τ` invariante em `τ`.

**Tupla:** covariante elemento a elemento; aridade deve coincidir.

**Array → Slice:**

```
[T; N] <: [T]   via coerção de referência: &[T; N] <: &[T]
```

### 6.2 Funções: contravariância

```
σ1 <: τ1   τ2 <: σ2
────────────────────────────
(τ1 -> τ2) <: (σ1 -> σ2)
```

Parâmetro contravariante, retorno covariante.

### 6.3 Nominais: sem subtipagem implícita

```
Ponto ≮ {x: float, y: float}  e vice-versa
```

Exceção: `struct` com `#[transparent]` ou `deref` coercion futura; hoje conversão exige `as` ou método `into()`.

### 6.4 Variância de genéricos

Declaração de variância por posição:

- `Vec<T>` invariante em `T` (por `&mut T` interno)
- `Opt<T>` covariante em `T`
- `fn(T)` contravariante

Anotação futura `in`/`out`; hoje inferida por análise de uso (se `T` só em saída → covariante).

### 6.5 Never (`!`) e `null`

- `!` (never, divergente) é subtipo de todo tipo: `! <: τ`. Usado por `panic()`, `loop`, `return`.
- `null` só compatível com `Opt<T>` ou `?T` via `Option::None`; não é subtipo universal (diferente de JS).

---

## 7. Genéricos

### 7.1 Parâmetros e bounds

```lumen
fn max<T: Ord>(a: T, b: T) -> T { if a > b { a } else { b } }

struct Mapa<K: Hash + Eq, V> { ... }
trait Index<K> { fn get(self, k: K) -> Opt<&Self::Item>; }

impl<K: Hash+Eq, V> Mapa<K,V> where K: Clone { fn new() -> Self { ... } }
```

Julgamento:

```
Γ, α: Type, α: Ord ⊢ e : τ
─────────────────────────────── (Gen-Intro)
Γ ⊢ fn max<α: Ord>(a: α, b: α) -> α { e } : ∀α:Ord. (α,α)->α
```

Instanciação é por inferência de argumento (turbofish opcional):

```lumen
max(3, 5)          // α=int inferido
max::<float>(1.0, 2.0) // explícito
```

### 7.2 Where clauses

`where` permite bounds não triviais:

```lumen
fn zip<A,B>(a: Vec<A>, b: Vec<B>) -> Vec<(A,B)> where A: Clone, B: Clone { ... }
```

### 7.3 Tipos associados

```lumen
trait Iter { type Item; fn next(mut self) -> Opt<Self::Item>; }

fn soma<I: Iter>(it: I) -> int where I::Item: Add<int> { ... }
```

Projeção `I::Item` é tipo; exige `I: Iter` em contexto.

### 7.4 Monomorfização vs apagamento

Decisão (§ SPEC.md): monomorfização para targets `native`/`wasm` (especialização), apagamento via dict passing para `vm` debug. Semântica observável idêntica; performance difere (ADR-002).

---

## 8. Traits

### 8.1 Declaração e implementação

```lumen
trait Mostrar { fn mostra(self) -> string; }
trait Clone: Mostrar { fn clone(self) -> Self; }

impl Mostrar for Ponto { fn mostra(self) -> string { return "ponto"; } }
impl<T: Mostrar> Mostrar for Opt<T> { fn mostra(self) -> string { match self { ... } } }
```

Regras de coerência (orphan rule simplificada):

- Impl deve estar no mesmo módulo de `trait` ou de `Self`. Duas impls para mesmo `(Trait, Self)` → erro.

### 8.2 Resolução

Resolução por busca de impl com unificação:

```
Γ ⊢ e : τ    Σ contém impl<T: Bounds> Trait for τ0   τ unifica τ0[Bounds]
────────────────────────────────────────────────────────────────────────────
Γ ⊢ e.mostra() : string   resolve para impl encontrada
```

Prioridade: impl específica > genérica; ambiguidade → erro com sugestão de turbofish.

### 8.3 Objetos de trait (dyn)

Futuro: `dyn Mostrar` como trait object estrutural (`Box<dyn Mostrar>`). Hoje: estático apenas; `dyn` reservado.

### 8.4 Traits builtin

`Add`, `Sub`, `Ord`, `Eq`, `Hash`, `Clone`, `Copy`, `Drop`, `Future`. `Copy` é marker: se `T: Copy`, semântica de move vira copy (ver `SEMANTICA.md`).

---

## 9. Coerções e Conversões

Coerções implícitas (inseridas pelo checker):

- `&mut T` → `&T`
- `&[T; N]` → `&[T]`
- `!` → qualquer `τ` (diverge)
- Record largura (§6.1) em posição de argumento

Conversões explícitas:

```lumen
let x: float = 42 as float;
let y: {x: float, y: float} = p as {x: float, y: float}; // Ponto -> record
```

`as` só permitido se relação de conversão registrada (numérica, referência, nominal→estrutural com mesmos campos).

---

## 10. Sistema de Efeitos `async`

`async fn` tem tipo `fn(...) -> Future<τ>`. `await: Future<τ> -> τ` dentro de async.

```
Γ ⊢ e : Future<τ>    Γ é async
────────────────────────────────
Γ ⊢ e.await : τ
```

`Future` é trait builtin com `poll`. Checker garante `await` só em contexto async, senão erro E027.

---

## 11. Diagnósticos de Tipo (exemplos)

```lumen
let x: int = "olá";
// erro[E030]: esperado `int`, encontrado `string`
//   --> main.lm:3:14
//    | let x: int = "olá";
//    |              ^^^^^^ esperado int

struct Ponto { x: float, y: float }
let p: {x: int, y: int} = Ponto { x: 1.0, y: 2.0 };
// erro[E040]: nominal `Ponto` não é subtipo de record `{x:int,y:int}`
// ajuda: tente `p as {x:float, y:float}` ou mude tipo de `p` para `Ponto`

fn id<T>(x: T) -> T { x }
let s: string = id(42);
// erro[E050]: não foi possível inferir `T` como `string`, `T=int` inferido do argumento
```

---

## 12. Soundness (esboço)

Teorema (preservação + progresso) para fragmento sem `unsafe` futuro:

- Se `Σ; ∅ ⊢ e : τ` e `e → e'` (small-step `SEMANTICA.md`), então `Σ; ∅ ⊢ e' : τ`.
- Se `e : τ` e `e` não é valor, existe `e'` tal que `e → e'`.

Prova por indução sobre derivação de tipagem; caso ownership requer lema de borrow uniqueness (§ SEMANTICA.md §4).

Nominal/estrutural distinção preserva soundness porque não há subtipagem nominal implícita que quebraria invariantes de representação.

---

*Fim de TIPOS.md*
