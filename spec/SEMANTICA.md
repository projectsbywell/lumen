# Lumen — Semântica Operacional e Denotacional

**Versão:** 0.1.0-draft  
**Status:** Normativa  
**Referencia:** `EBNF.md`, `TIPOS.md`; referenciado por `SPEC.md` §5

---

## 1. Preliminares: Domínios Semânticos

### 1.1 Valores

```
v ::= n:int | f:float | b:bool | c:char | s:string | null
    | (v, ..., v)              (* tupla *)
    | { l=v, ... }             (* record valor *)
    | C::V(v ...)              (* variante enum *)
    | clos(ρ, x, e)            (* closure *)
    | addr(a)                  (* referência / ponteiro *)
    | future(e)                (* valor future suspenso *)
```

Valor é forma normal irredutível. `clos` captura ambiente `ρ`.

### 1.2 Estado

```
ρ : Var → Addr              (* ambiente *)
μ : Addr → Val × Perm       (* store / heap *)
κ : StackFrame list         (* pilha de chamadas *)
ξ : ExcCont                 (* continuação de exceção, ver §5 *)
```

- `Perm = { Own, BorrowImm(a), BorrowMut(a), Moved }` — permissão de ownership (simplificado §4).
- `Addr` é localização abstrata (índice nat). Alocação `alloc(μ, v) = (a, μ[a↦(v,Own)])`.

Estado completo: `σ = (ρ, μ, κ, ξ)`. Configuração: `⟨e, σ⟩` ou `⟨s, σ⟩` para statements.

### 1.3 Resultados

```
r ::= Ok(v, σ') | Err(exn, σ') | Div  (* diverge *)
exn ::= Panic(v) | Throw(v) | Return(v) | Break(v) | Continue
```

`Panic` é irrecuperável salvo `catch` em `try` (futuro); hoje aborta. `Throw` para `?`/`Result`.

---

## 2. Semântica Operacional Small-Step

Relação `⟨e, σ⟩ → ⟨e', σ'⟩` (um passo). Fecho reflexivo-transitivo `→*`. Contextos de avaliação `E[·]` (call-by-value, esquerda→direita).

### 2.1 Contextos

```
E ::= [·] | E + e | v + E | E(e...) | v(E) | let x = E; e | E.field
    | E.await | E ? | if E {e} else {e} | match E { arms }
    | { l=E, ... } | (E, ...) | E as τ | &E | &mut E | *E
```

Regra de congruência:

```
⟨e, σ⟩ → ⟨e', σ'⟩
────────────────────── (Ctx)
⟨E[e], σ⟩ → ⟨E[e'], σ'⟩
```

### 2.2 Literais e operações primitivas

```
⟨n, σ⟩  já é valor                                    (Val)

⟨v1 + v2, σ⟩ → ⟨δ(+ , v1, v2), σ⟩   se v1,v2 : int|float   (Prim)
⟨v1 == v2, σ⟩ → ⟨(v1==v2), σ⟩
```

`δ` é função de interpretação primitiva (aritmética com overflow checked → Panic em debug, wrap em release - ver SPEC).

### 2.3 Variáveis e `let`

```
⟨x, (ρ,μ,κ,ξ)⟩ → ⟨v, (ρ,μ,κ,ξ)⟩   se ρ(x)=a, μ(a)=(v,_) e Perm permite leitura
                                senão Err(Moved) ou Err(Borrow)

⟨let x: τ = v; e, (ρ,μ,κ,ξ)⟩ → ⟨e, (ρ[x↦a], μ[a↦(v,Own)], κ, ξ)⟩  onde a fresh
⟨let mut x: τ = v; e, σ⟩     →  idem mas Perm=Own mutável

⟨x = v, (ρ,μ,κ,ξ)⟩ → ⟨v, (ρ, μ[a↦(v,Own)], κ, ξ)⟩  se ρ(x)=a e Perm=Own mut
                     senão Err(BorrowMut)
```

Shadowing permitido: novo `a` sombreia antigo.

### 2.4 Funções, chamada e `return`

Definição `fn f(x:τ)->σ { body }` elaborada em closure no topo:

```
ρ0 ⊢ fn f(x){body}  elaborates to  ρ0[f ↦ clos(ρ0, x, body)]
```

Chamada:

```
⟨(clos(ρc, x, e))(v), (ρ,μ,κ,ξ)⟩ → ⟨e[x↦a], (ρc[x↦a], μ[a↦(v,Own)], κ·frame(ρ), ξ)⟩
                                   a fresh, push frame

⟨return v, (ρ,μ,κ·frame(ρret), ξ)⟩ → ⟨v, (ρret, μ, κ, ξ)⟩ com sinal Return(v) propagado
⟨v, (ρ,μ,κ·frame(ρret), ξ)⟩ quando v é valor final do corpo → retorno implícito idem
```

Tail call não otimizada na semântica abstrata; otimização é de backend.

### 2.5 Campos, tuplas, structs, enums

```
⟨{l1=v1,...}.li, σ⟩ → ⟨vi, σ⟩
⟨(v0,...,vn).k, σ⟩ → ⟨vk, σ⟩   onde k é índice literal

⟨Ponto{x=e1,y=e2}, σ⟩ → ⟨{x=v1,y=v2}_Ponto, σ'⟩  (* tag nominal preservada *)
⟨Opt::Algum(v), σ⟩ → ⟨Algum(v)_Opt, σ⟩

⟨match v { p1=>e1, ... }, σ⟩ → ⟨eiθ, σ⟩  onde pi casa v com substituição θ (primeiro match)
```

Pattern matching é first-match, exaustividade verificada estaticamente.

### 2.6 Controle: `if`, `for`, `while`, `loop`

```
⟨if true {e1} else {e2}, σ⟩ → ⟨e1, σ⟩
⟨if false {e1} else {e2}, σ⟩ → ⟨e2, σ⟩

⟨for pat in e { body }, σ⟩  desugars para:
  ⟨{ let iter = e.into_iter(); loop { match iter.next() { Nenhum => break, Algum(pat) => body } } }, σ⟩

⟨while cond { body }, σ⟩ → ⟨if cond { body; while cond {body} } else {()}, σ⟩
⟨loop { body }, σ⟩ → ⟨body; loop{body}, σ⟩   (com handling de break/continue via ξ)

⟨break v, (ρ,μ,κ,ξloop)⟩ → propaga até ξloop que captura loop mais interno
```

`break` com valor: `let x = loop { break 42; }` → `x=42` (tipo do loop é tipo do `break`).

### 2.7 Blocos e sequenciamento

```
⟨{ s1; s2; ...; e }, σ⟩ → ⟨{ s1'; s2; ...; e }, σ'⟩ se s1 → s1'
⟨{ v; s2; ... }, σ⟩ → ⟨{ s2; ... }, σ⟩   (* v é unidade se s1 era statement sem valor *)
⟨{ v }, σ⟩ → ⟨v, σ⟩
```

`{}` vazio → `()` : unit.

---

## 3. Ownership / Borrow Simplificado

### 3.1 Modelo

Cada `Addr` tem estado:

```
Own        — dono único, pode mover, mutar se `mut`, emprestar
BorrowImm(n) — n empréstimos imutáveis ativos
BorrowMut  — empréstimo mutável exclusivo ativo
Moved      — valor movido, acesso é erro
```

Operações:

```
move(x):  requer μ(a)=(v,Own) ,  após: μ(a)=(v,Moved), retorna v (novo dono copia bits)
borrowImm(x):  requer Own ou BorrowImm, incrementa n, retorna addr(a) com Perm BorrowImm
borrowMut(x):  requer Own e n=0 e não BorrowMut, transita para BorrowMut, retorna addr(a)
drop(a): quando dono sai de escopo, μ(a) liberado; empréstimos devem ter terminado (n=0, não BorrowMut) senão erro estático (borrow checker)
```

Borrow checker estático garante que programas bem tipados nunca chegam a `Err(Borrow)` em runtime (preservação). Small-step inclui checks dinâmicos para especificação, mas compilador rejeita estaticamente.

### 3.2 Regras de tipagem para borrow (resumo)

```
Γ ⊢ x : τ   τ : Copy
─────────────────────  x usável após move (cópia)

Γ ⊢ x : τ   τ : !Copy
─────────────────────  move consome x; uso posterior → erro E038

Γ ⊢ &x : &τ     requer x: Own ou BorrowImm
Γ ⊢ &mut x : &mut τ  requer x: Own mut e nenhum borrow ativo
```

Exemplo:

```lumen
let s: string = "olá";      // s: Own string (string não é Copy)
let t = s;                  // move(s) → s=Moved, t=Own
// println(s)               // ERRO estático: uso de valor movido
let mut p = Ponto {x:1.0,y:2.0};
let r = &p;                 // BorrowImm(p) n=1
// p.x = 2.0                // ERRO: não pode mutar enquanto emprestado imut
let q = &mut p;             // ERRO se r vivo; OK após fim de escopo de r
```

### 3.3 Lifetimes elididos

Regra de desugar (§ TIPOS.md 5.3): `&τ` em assinatura vira `&'a τ`. Na semântica dinâmica, lifetime é escopo léxico do borrow: borrow expira no fim do bloco onde foi criado ou no último uso (NLL - non-lexical lifetimes) - especificado como "borrow expira quando não mais usado em continuação".

### 3.4 Roots do GC (v0.3)

O runtime possui coletor geracional (`runtime/gc.py`). Roots automáticos:
- Frames registrados via `registrar_frame`/`remover_frame` (VM stack).
- Globals via `definir_global`/`remover_global`.
- `marcar_root`/`desmarcar_root` são override manual, somados aos roots automáticos.

O borrow checker estático garante que a maioria dos programas não precisa de roots manuais.

---

## 4. Semântica de `async` / `await`

```
⟨async { e }, σ⟩ → ⟨future( clos(σ.ρ, (), e) ), σ⟩   (* cria future sem executar *)

⟨future(e).await, σ⟩ →  (* se em contexto async *)
    se e →* v  então ⟨v, σ'⟩
    senão suspende: retorna Poll::Pending e registra waker; re-agenda quando pronto
```

Modelo formal: `Future` é `trait` com `poll: fn(mut self, waker) -> Poll<τ>`. `await` desugars para loop de poll:

```
e.await  ≡  { let mut fut = e; loop { match fut.poll(waker) { Ready(v) => break v, Pending => yield } } }
```

Efeito é cooperativo; semântica denotacional vê `Future<τ>` como computação que produz `τ` eventualmente.

---

## 5. Exceções, `panic` e `?` (Result)

Lumen distingue `panic` (bug) e `Result` (erro recuperável).

### 5.1 Panic

```
⟨panic(v), σ⟩ → Err(Panic(v), σ)   propaga até topo; se não capturado, aborta e imprime v
```

`panic` tem tipo `!` (`! <: τ`), então `let x: int = panic("ops");` é bem tipado mas diverge.

### 5.2 Result e `?`

```
enum Result<T,E> { Ok(T), Erro(E) }

⟨e ?, σ⟩  ≡  ⟨match e { Ok(v) => v, Erro(e) => return Erro(e) }, σ⟩  se em fn -> Result
          ≡  ⟨match e { Ok(v) => v, Erro(e) => panic(e) }, σ⟩       se não (hoje erro)
```

Small-step para `?`:

```
⟨Ok(v) ?, σ⟩ → ⟨v, σ⟩
⟨Erro(e) ?, σ⟩ → ⟨return Erro(e), σ⟩   (* early return se função retorna Result *)
```

`try`/`catch` futuro desugar para match em `Result`.

---

## 6. Semântica Denotacional (Esboço)

Domínios `D`:

```
D_int = ℤ⊥
D_float = ℝ⊥
D_bool = {true,false}⊥
D_string = String⊥
D_τ = (D_τ1 × ... × D_τn)⊥  para tupla
D_{l:τ} = (Label → D_τ)⊥   para record
D_{C} = Σ_{V} (D_payload)  para enum
D_{&τ} = Addr
D_{fn(A)->B} = (D_A → D_B)  (função contínua)
D_{Future<τ>} = (Waker → Poll<D_τ>)
Poll<X> = Pending | Ready(X)
D_! = ∅  (domínio vazio)
```

Função de denotação `⟦·⟧ : Expr → Env → Store → (D × Store)`:

```
⟦n⟧ ρ μ = (n, μ)
⟦x⟧ ρ μ = (μ(ρ(x)).val, μ)
⟦e1 + e2⟧ ρ μ = let (v1, μ1)=⟦e1⟧ρ μ in let (v2, μ2)=⟦e2⟧ρ μ1 in (v1+v2, μ2)
⟦let x = e1; e2⟧ ρ μ = let (v1, μ1)=⟦e1⟧ρ μ in let a=fresh in ⟦e2⟧ρ[x↦a] μ1[a↦(v1,Own)]
⟦if c {t} else {e}⟧ ρ μ = let (vc, μ1)=⟦c⟧ρ μ in if vc then ⟦t⟧ρ μ1 else ⟦e⟧ρ μ1
⟦match e {p=>b}⟧ ρ μ = let (v, μ1)=⟦e⟧ρ μ in ⟦bθ⟧ρ μ1 onde θ = match(v,p)
⟦fn(x){body}⟧ ρ μ = (λ v. λ μ'. ⟦body⟧ρ[x↦a] μ'[a↦v], μ)  (* closure *)
⟦e1(e2)⟧ ρ μ = let (f, μ1)=⟦e1⟧ρ μ in let (v, μ2)=⟦e2⟧ρ μ1 in f(v)(μ2)
⟦&x⟧ ρ μ = (ρ(x), μ)   (* denota endereço *)
⟦*p⟧ ρ μ = let (a, μ1)=⟦p⟧ρ μ in (μ1(a).val, μ1)
⟦async {e}⟧ ρ μ = (λ waker. Pending até poll, μ)  (* futura computação *)
⟦e.await⟧ ρ μ = let (fut, μ1)=⟦e⟧ρ μ in fut(waker)(μ1)  (* força *)
⟦panic(v)⟧ ρ μ = (⊥_{panic}, μ)  (* bottom com efeito *)
```

**Composicionalidade:** `⟦{s1; s2}⟧ = ⟦s2⟧ ∘ ⟦s1⟧`.

**Correção:** Para todo `e, σ`, se `⟨e,σ⟩ →* ⟨v,σ'⟩` então `⟦e⟧(σ.ρ)(σ.μ) = (v, σ'.μ)` (adequação). Prova por indução sobre passos, usando lema de substituição para closures.

**Exemplo denotacional:**

```lumen
let x: int = 42; let mut y = x + 1
```

```
⟦let x=42⟧ρ μ = ((), μ1) onde μ1 = μ[a_x↦(42,Own)]
⟦let mut y = x+1⟧ρ[x↦a_x] μ1 = ((), μ2) onde v_y = 42+1=43, μ2= μ1[a_y↦(43,Own)]
Resultado: ρ' = ρ[x↦a_x, y↦a_y], μ' = {a_x:42, a_y:43}
```

---

## 7. Não-determinismo e Concorrência

- `async` tasks são agendadas cooperativamente; semântica interleaving não-determinística entre `await` points, mas determinística dentro de basic block.
- `Send`/`Sync` markers (futuro) restringem quais `τ` podem cruzar `await` / threads. Hoje single-threaded `vm`, então `Send` é trivial.

---

## 8. Resumo de Regras Small-Step (tabela)

| Construto | Regra chave |
|-----------|-------------|
| `let x=v; e` | alloc fresh `a`, extend ρ |
| `x = v` | check `mut` + `Own`, update μ |
| `&x` / `&mut x` | check borrow, retorna addr |
| `f(v)` | push frame, bind param |
| `return v` | pop até frame, sinal Return |
| `if` / `match` | branch por valor |
| `for` | desugar para `into_iter`+`loop`+`match` |
| `async` | cria `future` sem executar |
| `await` | poll loop, yield se Pending |
| `?` | `Ok→v`, `Erro→return Erro` |
| `panic` | `Err(Panic)` propaga |

---

*Fim de SEMANTICA.md — small-step é normativa; denotacional é explicativa e deve coincidir.*
