# Lumen — Gramática EBNF Completa

**Versão:** 0.1.0-draft  
**Status:** Normativa  
**Depende de:** —  
**Referenciado por:** `SPEC.md` §3, `TIPOS.md` §1, `SEMANTICA.md` §1

> Esta gramática é a fonte da verdade sintática. Todo programa que passa no parser deve ser derivável de `Programa`. Notação: ISO/IEC 14977 EBNF estendida (`=` definição, `;` término, `|` alternativa, `[ ]` opcional, `{ }` repetição 0..n, `( )` agrupamento, `"` terminal string, `(* comentário *)`).

---

## 1. Convenções Léxicas

### 1.1 Conjunto de caracteres e whitespace

```ebnf
Programa        = { Espaco | Comentario }, ModuloDecl, { ImportDecl }, { ItemTopo }, [ Espaco ] ;

Espaco         = ( " " | "\t" | "\r" | "\n" ) ;
Comentario     = ComentarioLinha | ComentarioBloco ;
ComentarioLinha= "//", { Caractere - "\n" }, "\n" ;
ComentarioBloco= "/*", { Caractere | ComentarioBloco }, "*/" ;
```

Comentários são ignorados pelo lexer exceto quando dentro de literais. `/*` aninhável.

### 1.2 Palavras-chave (reservadas)

```
module  import  pub  fn  let  mut  const  struct  enum  trait  impl  for  where
if  else  match  for  while  loop  break  continue  return
async  await  macro  type  self  Self  super  crate  as  use
in  is  true  false  null
test  bench  (* atributos de teste via anotação *)
```

Qualquer keyword pode ser usada como identificador se prefixada com `r#` (raw identifier): `r#type`, `r#match`.

### 1.3 Identificadores e caminhos

```ebnf
Ident          = ( Letra | "_" ), { Letra | Digito | "_" } ;
IdentRaw       = "r#", Ident ;
IdentQualif    = Ident | IdentRaw ;
Caminho        = IdentQualif, { "::", IdentQualif } ;
CaminhoAbs     = [ "::" ], Caminho ;
Letra          = "A" … "Z" | "a" … "z" | "_" ;  (* simplificado; Unicode XID_Start *)
Digito         = "0" … "9" ;
```

Por convenção: `UpperCamelCase` para tipos/traits, `snake_case` para valores/funções, `SCREAMING_SNAKE` para const.

### 1.4 Literais

```ebnf
Literal        = LiteralInt | LiteralFloat | LiteralString | LiteralChar | LiteralBool | LiteralNull ;
LiteralInt     = [ "-" ], ( "0" | [ "1" … "9", { Digito | "_" } ] ), [ SufixoTipoInt ] ;
SufixoTipoInt  = "i8" | "i16" | "i32" | "i64" | "u8" | "u16" | "u32" | "u64" | "int" | "uint" ;
LiteralFloat   = [ "-" ], Digito, { Digito | "_" }, ".", { Digito | "_" },
                 [ ( "e" | "E" ), [ "+" | "-" ], Digito, { Digito | "_" } ],
                 [ "f32" | "f64" | "float" ] ;
LiteralString  = '"', { CaractereString }, '"' | LiteralStringRaw ;
LiteralStringRaw = "r", { "#" }, '"', { Caractere }, '"', { "#" } ;
CaractereString= Caractere - ( '"' | "\\" | "\n" ) | Escape ;
Escape         = "\\", ( "n" | "r" | "t" | "\\" | '"' | "'" | "0" | "u", "{", HexDigito, { HexDigito }, "}" ) ;
LiteralChar    = "'", ( Caractere - "'" | Escape ), "'" ;
LiteralBool    = "true" | "false" ;
LiteralNull    = "null" ;
HexDigito      = Digito | "a" … "f" | "A" … "F" ;
Caractere      = ? qualquer Unicode escalar ? ;
```

Ex.: `42`, `42int`, `3.14f64`, `"olá\n"`, `r#"raw "quote""#`, `'x'`, `true`.

---

## 2. Programa, Módulos e Imports

```ebnf
ModuloDecl     = "module", Ident, { ".", Ident } , [ ";" | NovaLinha ] ;
ImportDecl     = "import", CaminhoAbs, [ "as", IdentQualif ], 
                 [ "{", ListaImport, "}" ], ";" ;
ListaImport    = ImportItem, { ",", ImportItem }, [ "," ] ;
ImportItem     = IdentQualif, [ "as", IdentQualif ] | "*" | "self" ;

ItemTopo       = Atributo, ItemVisivel ;
ItemVisivel    = [ Visibilidade ], Item ;
Visibilidade   = "pub" [ "(" , "crate" | "super" | "self", ")" ] ;
Atributo       = { "#", "[", ConteudoAtributo, "]" } ;
ConteudoAtributo = IdentQualif, [ "(", ListaAtribArg, ")" ] | Caminho, [ "(", ListaAtribArg, ")" ] ;
ListaAtribArg  = AtribArg, { ",", AtribArg } ;
AtribArg       = Literal | IdentQualif, [ "=", Literal ] | Caminho ;

Item           = DeclFuncao
               | DeclLetTopo
               | DeclConst
               | DeclTipoAlias
               | DeclStruct
               | DeclEnum
               | DeclTrait
               | DeclImpl
               | DeclMacro
               | DeclModuloAninhado ;

DeclModuloAninhado = "module", IdentQualif, "{", { ItemTopo }, "}" | "module", IdentQualif, ";" ;
DeclLetTopo    = "let", [ "mut" ], IdentQualif, [ ":", Tipo ], "=", Expressao, ";" ;
DeclConst      = "const", IdentQualif, [ ":", Tipo ], "=", Expressao, ";" ;
DeclTipoAlias  = "type", IdentQualif, [ ParametrosGenericos ], "=", Tipo, ";" ;
```

Exemplos normativos:

```lumen
module hello
import std.io
import std.collections.{HashMap, Vec as Vetor}
import std.math.*

pub fn main() -> int { io.println("olá"); return 0; }
```

---

## 3. Funções

```ebnf
DeclFuncao     = [ "async" ], "fn", IdentQualif, ParametrosGenericos,
                 ListaParametros, [ "->", Tipo ], [ ClWhere ], CorpoFuncao ;
ListaParametros= "(", [ Parametro, { ",", Parametro }, [ "," ] ], ")" ;
Parametro      = [ "mut" ], IdentQualif, ":", Tipo | "self" | "&", [ "mut" ], "self" | "&mut self" ;
CorpoFuncao    = Bloco | ";" ;
Bloco          = "{", { Statement }, "}" ;
ParametrosGenericos = "<", ParametroGenerico, { ",", ParametroGenerico }, [ "," ], ">" ;
ParametroGenerico= IdentQualif, [ ":", LimiteTrait, { "+", LimiteTrait } ] | IdentQualif, "=", Tipo ;
LimiteTrait    = CaminhoAbs, [ "<", ArgGenerico, { ",", ArgGenerico }, ">" ] ;
ArgGenerico    = Tipo | Literal | CaminhoAbs ;
ClWhere        = "where", PredicadoWhere, { ",", PredicadoWhere }, [ "," ] ;
PredicadoWhere = IdentQualif, ":", LimiteTrait, { "+", LimiteTrait } | Tipo, ":", LimiteTrait ;
```

Função pode ter atributos `#[inline]`, `#[test]`, etc.

```lumen
pub fn soma<T: Add + Copy>(a: T, b: T) -> T where T: Clone { return a + b; }
pub async fn fetch(url: string) -> Result<string, IoError> { let data = await http.get(url); return data; }
```

---

## 4. Variáveis: `let` / `mut`

```ebnf
DeclLet        = "let", [ "mut" ], Padrao, [ ":", Tipo ], [ "=", Expressao ], ";" ;
Padrao         = PadraoIrrefutavel | PadraoRefutavel ;
PadraoIrrefutavel = IdentQualif, [ "mut", IdentQualif ] | "_" | PadraoTupla | PadraoStruct ;
PadraoRefutavel= Literal | IdentQualif, [ "(", ListaPadrao, ")" ] | PadraoStruct | PadraoTupla
               | PadraoSlice | PadraoOr | PadraoBind ;
PadraoStruct   = CaminhoAbs, "{", [ CampoPadrao, { ",", CampoPadrao }, [ "," ] ], "}" ;
CampoPadrao    = IdentQualif, [ ":", Padrao ] | IdentQualif ;
PadraoTupla    = "(", [ Padrao, { ",", Padrao }, [ "," ] ], ")" ;
PadraoSlice    = "[", [ Padrao, { ",", Padrao } ], "]" ;
PadraoOr       = Padrao, "|", Padrao ;
PadraoBind     = IdentQualif, "@", Padrao ;
ListaPadrao    = Padrao, { ",", Padrao }, [ "," ] ;
```

Semântica de `mut`: ver `SEMANTICA.md` §4. `let` sem `mut` cria binding imutável; `let mut` permite reatribuição.

```lumen
let x: int = 42;
let mut y = x + 1;
let (a, b): (int, float) = (1, 2.0);
let Ponto { x, y } = origem;
```

---

## 5. Tipos

```ebnf
Tipo           = TipoPrim | TipoCaminho | TipoTupla | TipoArray | TipoSlice
               | TipoFuncao | TipoRef | TipoPtr | TipoNever | TipoInfer | TipoAnonStruct ;
TipoPrim       = "int" | "uint" | "i8" | "i16" | "i32" | "i64"
               | "u8" | "u16" | "u32" | "u64" | "float" | "f32" | "f64"
               | "bool" | "char" | "string" | "str" ;
TipoCaminho    = CaminhoAbs, [ "<", ArgGenerico, { ",", ArgGenerico }, ">" ] ;
TipoTupla      = "(", [ Tipo, { ",", Tipo }, [ "," ] ], ")" ;  (* () é unit *)
TipoArray      = "[", Tipo, ";", Expressao, "]" ;
TipoSlice      = "[", Tipo, "]" ;
TipoFuncao     = "fn", "(", [ Tipo, { ",", Tipo } ], ")", [ "->", Tipo ] ;
TipoRef        = "&", [ "mut" ], Tipo ;
TipoPtr        = "*", [ "mut" | "const" ], Tipo ;
TipoNever      = "!" ;
TipoInfer      = "_" ;  (* para inferência local: let x: _ = 42; *)
TipoAnonStruct = "{", CampoTipoAnon, { ",", CampoTipoAnon }, [ "," ], "}" ;
CampoTipoAnon  = IdentQualif, ":", Tipo ;
```

Tipos estruturais: `TipoAnonStruct`, `TipoTupla`, `TipoFuncao`. Tipos nominais: `TipoCaminho` que resolve para `struct/enum/trait`.

```lumen
type Par = (int, int);
type Callback = fn(string) -> bool;
let p: {x: float, y: float} = {x: 1.0, y: 2.0}; // estrutural
```

---

## 6. Struct / Enum / Trait / Impl

```ebnf
DeclStruct     = "struct", IdentQualif, ParametrosGenericos, [ ClWhere ],
                 ( ";" | "{", ListaCampoStruct, "}" | "(", ListaCampoTupla, ")", ";" ) ;
ListaCampoStruct = CampoStruct, { ",", CampoStruct }, [ "," ] ;
CampoStruct    = [ Visibilidade ], IdentQualif, ":", Tipo ;
ListaCampoTupla= [ Visibilidade ], Tipo, { ",", [ Visibilidade ], Tipo }, [ "," ] ;

DeclEnum       = "enum", IdentQualif, ParametrosGenericos, [ ClWhere ],
                 "{", [ VarianteEnum, { ",", VarianteEnum }, [ "," ] ], "}" ;
VarianteEnum   = IdentQualif, [ "(", [ Tipo, { ",", Tipo } ], ")" | "{", ListaCampoStruct, "}" ] ;

DeclTrait      = "trait", IdentQualif, ParametrosGenericos, [ ":", LimiteTrait, { "+", LimiteTrait } ],
                 [ ClWhere ], "{", { ItemTrait }, "}" ;
ItemTrait      = [ Visibilidade ], ( DeclFuncaoAssociada | DeclTipoAssociado | DeclConstAssociada ) ;
DeclFuncaoAssociada = [ "async" ], "fn", IdentQualif, ParametrosGenericos,
                       ListaParametros, [ "->", Tipo ], [ ClWhere ], ( Bloco | ";" ) ;
DeclTipoAssociado  = "type", IdentQualif, [ ":", LimiteTrait, { "+", LimiteTrait } ], [ "=", Tipo ], ";" ;
DeclConstAssociada = "const", IdentQualif, ":", Tipo, [ "=", Expressao ], ";" ;

DeclImpl       = "impl", ParametrosGenericos, [ Tipo, "for" ], CaminhoAbs,
                 [ ClWhere ], "{", { ItemImpl }, "}" ;
ItemImpl       = [ Visibilidade ], ( DeclFuncao | DeclTipoAlias | DeclConst ) ;
```

Exemplos:

```lumen
struct Ponto { x: float, y: float }
enum Opt<T> { Nenhum, Algum(T) }
trait Mostrar { fn mostra(self) -> string; }
impl Mostrar for Ponto { fn mostra(self) -> string { return "{x:\(self.x)}"; } }
impl<T> Clone for Opt<T> where T: Clone { }
struct Wrapper<T>(T); // tuple struct
```

---

## 7. Statements e Expressões

```ebnf
Statement      = DeclLet
               | ExpressaoStmt
               | DeclFuncao  (* apenas em blocos? permitido *)
               ;
ExpressaoStmt  = Expressao, [ ";" ] ;

Expressao      = ExpressaoAtribuicao ;
ExpressaoAtribuicao = ExpressaoControle | ExpressaoLogica, [ OpAtrib, ExpressaoAtribuicao ] ;
OpAtrib        = "=" | "+=" | "-=" | "*=" | "/=" | "%=" | "&=" | "|=" | "^=" | "<<=" | ">>=" ;

ExpressaoControle= ExpressaoIf | ExpressaoMatch | ExpressaoLoop | ExpressaoRetorno
                 | ExpressaoBreak | ExpressaoContinue ;
ExpressaoIf    = "if", Expressao, Bloco, [ "else", ( Bloco | ExpressaoIf ) ] ;
ExpressaoMatch = "match", Expressao, "{", { BracoMatch, [ "," ] }, "}" ;
BracoMatch     = Padrao, [ GuardMatch ], "=>", ( Expressao | Bloco ) ;
GuardMatch     = "if", Expressao ;

ExpressaoLoop  = LoopFor | LoopWhile | LoopInfinito ;
LoopFor        = "for", Padrao, "in", Expressao, Bloco ;
LoopWhile      = "while", Expressao, Bloco ;
LoopInfinito   = "loop", Bloco ;
ExpressaoRetorno = "return", [ Expressao ] ;
ExpressaoBreak = "break", [ Expressao | IdentQualif ] ;
ExpressaoContinue= "continue", [ IdentQualif ] ;

ExpressaoLogica= ExpressaoBinaria ;
ExpressaoBinaria = ExpressaoUnaria, { OpBinario, ExpressaoUnaria } ;
OpBinario      = "||" | "&&" | "==" | "!=" | "<" | ">" | "<=" | ">="
               | "|" | "^" | "&" | "<<" | ">>" | "+" | "-" | "*" | "/" | "%" ;
ExpressaoUnaria= [ OpUnario ], ExpressaoPosfixa ;
OpUnario       = "-" | "!" | "~" | "*" | "&"  [ "mut" ] | "await" | "?" ;
ExpressaoPosfixa= ExpressaoPrimaria, { SufixoPosfixo } ;
SufixoPosfixo  = "(" , [ ListaArgs ], ")"         (* chamada *)
               | "[" , Expressao, "]"            (* index *)
               | ".", IdentQualif                 (* acesso campo *)
               | ".", LiteralInt                  (* acesso tupla: t.0 *)
               | "?"                              (* propagação de erro *)
               | "as", Tipo ;                     (* cast *)

ExpressaoPrimaria = Literal | CaminhoAbs | "self" | "Self"
                  | "(", [ Expressao, { ",", Expressao }, [ "," ] ], ")"
                  | "[", [ Expressao, { ",", Expressao }, [ "," ] ], "]"
                  | "{", { Statement }, [ Expressao ], "}"
                  | Bloco
                  | ExpressaoStruct
                  | ExpressaoClosure ;

ExpressaoStruct= CaminhoAbs, "{", [ CampoInit, { ",", CampoInit }, [ "," ] ], "}" ;
CampoInit      = IdentQualif, [ ":", Expressao ] | "..", Expressao ;
ExpressaoClosure= [ "async" ], "|", [ ListaClosureParam ], "|", ( Expressao | Bloco ) ;
ListaClosureParam= ClosureParam, { ",", ClosureParam } ;
ClosureParam   = [ "mut" ], IdentQualif, [ ":", Tipo ] ;

ListaArgs      = Expressao, { ",", Expressao }, [ "," ] ;
```

Precedência (da mais alta para mais baixa):
1. `() [] .` (pós-fixa), `as`
2. unários `! - * & &mut await ?`
3. `* / %`
4. `+ -`
5. `<< >>`
6. `&`
7. `^`
8. `|`
9. `== != < > <= >= is in`
10. `&&`
11. `||`
12. `=>` (match arm), `=` `+=` ... (atribuição, direita-associativa)

```lumen
if x > 0 { io.println("pos"); } else { io.println("neg"); };
match v { 0 => "zero", _ => "outro" }
for i in 0..10 { if i == 5 { break; } }
while ok { ok = step(); }
```

---

## 8. Genéricos

Já definidos em `ParametrosGenericos` / `ArgGenerico`. Regras adicionais:

```ebnf
(* Uso em chamada turbofish opcional *)
ExpressaoTurbofish = CaminhoAbs, "::", "<", ArgGenerico, { ",", ArgGenerico }, ">" ;
```

```lumen
fn id<T>(x: T) -> T { return x; }
let a = id<int>(42);
let b = Vec::<int>::new();
```

---

## 9. Async / Await

```ebnf
ExpressaoAwait = ExpressaoPosfixa, "await" | "await", ExpressaoPosfixa ; (* pós-fixa preferida *)
BlocoAsync     = "async", Bloco ;
```

`async fn` desugars para `fn` que retorna `Future<Output>`. `await` só permitido dentro de `async fn` ou `async` bloco. `async { ... }` cria `Future`.

```lumen
async fn carregar(caminho: string) -> string {
    let f = std.fs.open(caminho).await;
    return f.read_to_string().await;
}
let fut = async { 42 };
```

---

## 10. Macros

```ebnf
DeclMacro      = "macro", IdentQualif, ParametrosMacro, CorpoMacro ;
ParametrosMacro= "(", [ IdentQualif, { ",", IdentQualif } ], ")" | "!" ;
CorpoMacro     = "{", { MacroRegra }, "}" | "=>", Expressao, ";" ;
MacroRegra     = "(", PadraoMacro, ")", "=>", "(", ExpansaoMacro, ")", ";" ;
PadraoMacro    = { TokenMacro | CapturaMacro } ;
CapturaMacro   = "$", IdentQualif, ":", TipoCaptura ;
TipoCaptura    = "expr" | "stmt" | "ty" | "ident" | "path" | "block" | "literal" | "tt" ;
ExpansaoMacro  = { TokenMacro | "$", IdentQualif } ;

InvocacaoMacro = CaminhoAbs, "!", ( "(", ListaToken, ")" | "[", ListaToken, "]" | "{", ListaToken, "}" ) ;
ListaToken     = { TokenMacro } ;
TokenMacro     = ? qualquer token exceto delimitador de fechamento ? ;
```

Macros são higiênicas; expansão ocorre antes de resolução de nomes (fase 1).

```lumen
macro vec_of(exprs: expr) => { Vec::from([$(exprs),*]) }
let v = vec_of![1, 2, 3];
println!("olá \(x)");
```

`println!` é macro builtin.

---

## 11. Atributos e Anotações de Teste

```ebnf
AtributoTeste  = "#", "[", "test", [ "(", ArgTeste, { ",", ArgTeste }, ")" ], "]"
               | "#", "[", "bench", [ "(", ArgTeste, { ",", ArgTeste }, ")" ], "]"
               | "#", "[", "should_panic", [ "(", ArgTeste, ")" ], "]" ;
ArgTeste       = IdentQualif, [ "=", Literal ] ;
```

Atributos podem aparecer sobre qualquer `Item` ou `DeclFuncao`. `#[test]` marca função de teste descoberta por `lumen test`.

```lumen
#[test]
fn test_soma() {
    assert(soma(2,2) == 4);
}

#[test(should_panic)]
fn test_panic() { panic("ops"); }

#[bench]
fn bench_sort() { /* ... */ }
```

Outros atributos: `#[inline]`, `#[derive(Clone, Debug)]`, `#[allow(unused)]`, `#[cfg(target="wasm")]`.

---

## 12. Programa de Exemplo Completo (normativo)

```lumen
module hello
import std.io
import std.math.{sqrt}

pub struct Ponto { x: float, y: float }

pub enum Opt<T> { Nenhum, Algum(T) }

pub trait Area { fn area(self) -> float; }

impl Area for Ponto {
    fn area(self) -> float { return self.x * self.y; }
}

pub fn distancia(a: Ponto, b: Ponto) -> float {
    let dx = a.x - b.x;
    let dy = a.y - b.y;
    return sqrt(dx*dx + dy*dy);
}

pub async fn buscar(p: Ponto) -> string {
    let d = distancia(p, Ponto { x: 0.0, y: 0.0 });
    if d > 10.0 {
        return "longe";
    } else {
        return "perto";
    }
}

macro log(msg: expr) => { io.println($msg) }

#[test]
fn test_distancia() {
    let a = Ponto { x: 0.0, y: 0.0 };
    let b = Ponto { x: 3.0, y: 4.0 };
    assert(distancia(a,b) == 5.0);
}

pub fn main() -> int {
    let x: int = 42;
    let mut y = x + 1;
    if x > 0 { y += 1; } else { y -= 1; }
    let v = 0;
    let s = match v { 0 => "zero", _ => "outro" };
    io.println(s);
    log!("olá \(y)");
    return 0;
}
```

---

## 13. Gramática Léxica Resumida (para geradores)

Para implementação: lexer deve produzir tokens: `IDENT`, `LITERAL_INT`, `LITERAL_FLOAT`, `LITERAL_STRING`, `LITERAL_CHAR`, `KEYWORD`, `SYMBOL` (`::`, `=>`, `->`, `..`, `...`, operadores), `ATRIBUTO`. Parser é LL(k) com 2 lookahead para distinguir `struct` expressão vs tipo.

---

*Fim de EBNF.md — qualquer divergência entre exemplos e produção, a produção prevalece.*
