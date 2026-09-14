# Referência da API Lumen (stdlib v0.1)

> Gerado por `docs/gen.py` em 2026-09-13 · spec Lumen v0.1.0.
> Para regenerar: `python3 docs/gen.py --src <fontes> --merge docs/API.md`
> (quando `stdlib/` estiver populada: `--src stdlib`).

<!-- fonte: stdlib_api.lum -->
Biblioteca padrão do Lumen — superfície documentada v0.1.

Este arquivo é a **fonte de documentação** da stdlib: cada item aqui
descreve uma função, tipo ou módulo real de `stdlib/` com a mesma
assinatura. `docs/API.md` é gerado a partir daqui com:

```sh
python3 docs/gen.py --src docs/stdlib_api.lum --merge docs/API.md
```

Quando `stdlib/` estiver populada, regenere com `--src stdlib`.

Convenções usadas em todas as assinaturas:
- `str` é texto UTF-8 imutável; `String` é o dono mutável.
- `Result<T, E>` é `Ok(valor)` ou `Err(erro)`; `?` propaga o `Err`.
- `Option<T>` é `Some(valor)` ou `None`.

## `mod` io

```lum
mod io {
```

Módulo `std::io` — entrada e saída no console.

## `fn` io::println

```lum
pub fn println(text: str) { }
```

Imprime `text` seguido de `\n` na saída padrão.

Exemplo:
```lum
use std::io;
fn main() { io::println("olá"); }
```

## `fn` io::print

```lum
pub fn print(text: str) { }
```

Imprime `text` sem nova linha final.

## `fn` io::read_line

```lum
pub fn read_line() -> Result<String, str> { }
```

Lê uma linha da entrada padrão (sem o `\n`). Retorna `Err` em EOF.

## `fn` io::args

```lum
pub fn args() -> Vec<String> { }
```

Lê todos os argumentos da linha de comando, incluindo o programa.

## `mod` str

```lum
mod str {
```

Módulo `std::str` — utilidades de texto UTF-8.

## `fn` str::len

```lum
pub fn len(s: str) -> i32 { }
```

Número de caracteres (não bytes) de `s`.

## `fn` str::upper

```lum
pub fn upper(s: str) -> String { }
```

Devolve `s` em maiúsculas.

## `fn` str::lower

```lum
pub fn lower(s: str) -> String { }
```

Devolve `s` em minúsculas.

## `fn` str::split

```lum
pub fn split(s: str, sep: str) -> Vec<String> { }
```

Divide `s` pelo separador `sep`.

## `fn` str::join

```lum
pub fn join(partes: Vec<str>, sep: str) -> String { }
```

Junta `partes` com `sep` entre elas.

## `fn` str::trim

```lum
pub fn trim(s: str) -> String { }
```

Remove espaços no início e no fim.

## `fn` str::to_int

```lum
pub fn to_int(s: str) -> Result<i32, str> { }
```

Converte `s` em `i32`. Retorna `Err` se não for número.

## `fn` str::from_int

```lum
pub fn from_int(n: i32) -> String { }
```

Converte `n` em `String` decimal.

## `fn` str::from_float

```lum
pub fn from_float(x: f64) -> String { }
```

Converte `x` em `String` (`Display`, sem precisão fixa).

## `mod` vec

```lum
mod vec {
```

Módulo `std::vec` — vetores dinâmicos `Vec<T>`.

## `fn` vec::novo

```lum
pub fn novo<T>() -> Vec<T> { }
```

Cria um vetor vazio.

## `fn` vec::len

```lum
pub fn len<T>(v: Vec<T>) -> i32 { }
```

Número de elementos.

## `fn` vec::push

```lum
pub fn push<T>(v: mut Vec<T>, x: T) { }
```

Adiciona `x` ao final (requer `mut`).

## `fn` vec::pop

```lum
pub fn pop<T>(v: mut Vec<T>) -> Option<T> { }
```

Remove e retorna o último elemento, ou `None` se vazio.

## `fn` vec::map

```lum
pub fn map<T, U>(v: Vec<T>, f: fn(T) -> U) -> Vec<U> { }
```

Aplica `f` a cada elemento e devolve o novo vetor.

## `fn` vec::filter

```lum
pub fn filter<T>(v: Vec<T>, f: fn(T) -> bool) -> Vec<T> { }
```

Mantém só os elementos onde `f` retorna `true`.

## `mod` map

```lum
mod map {
```

Módulo `std::map` — mapas `Map<K, V>`.

## `fn` map::novo

```lum
pub fn novo<K, V>() -> Map<K, V> { }
```

Cria um mapa vazio.

## `fn` map::insert

```lum
pub fn insert<K, V>(m: mut Map<K, V>, chave: K, valor: V) { }
```

Insere `chave -> valor` (substitui se existir).

## `fn` map::get

```lum
pub fn get<K, V>(m: Map<K, V>, chave: K) -> Option<V> { }
```

Busca `chave`. Retorna `Some(valor)` ou `None`.

## `fn` map::has

```lum
pub fn has<K, V>(m: Map<K, V>, chave: K) -> bool { }
```

`true` se `chave` existe no mapa.

## `fn` map::remove

```lum
pub fn remove<K, V>(m: mut Map<K, V>, chave: K) -> Option<V> { }
```

Remove `chave` e retorna o valor, ou `None`.

## `mod` math

```lum
mod math {
```

Módulo `std::math` — matemática básica.

## `fn` math::sqrt

```lum
pub fn sqrt(x: f64) -> Result<f64, str> { }
```

Raiz quadrada. `Err` para valores negativos.

## `fn` math::pow

```lum
pub fn pow(base: f64, exp: f64) -> f64 { }
```

`base` elevado a `exp`.

## `fn` math::fat

```lum
pub fn fat(n: i32) -> Result<i32, str> { }
```

Fatorial de `n` (`n!`). `Err` para `n < 0`.

## `fn` math::abs

```lum
pub fn abs(x: f64) -> f64 { }
```

Valor absoluto.

## `fn` math::min

```lum
pub fn min(a: f64, b: f64) -> f64 { }
```

Menor dos dois valores.

## `fn` math::max

```lum
pub fn max(a: f64, b: f64) -> f64 { }
```

Maior dos dois valores.

## `fn` math::mdiv

```lum
pub fn mdiv(a: i32, b: i32) -> i32 { }
```

Resto da divisão que funciona para negativos.

## `const` math::PI

```lum
pub const PI: f64 = 3.141592653589793;
```

Constante π.

## `mod` fs

```lum
mod fs {
```

Módulo `std::fs` — arquivos.

## `fn` fs::read_arquivo

```lum
pub fn read_arquivo(caminho: str) -> Result<String, str> { }
```

Lê o arquivo inteiro como texto.

## `fn` fs::write_arquivo

```lum
pub fn write_arquivo(caminho: str, conteudo: str) -> Result<(), str> { }
```

Escreve `conteudo` no arquivo (cria ou trunca).

## `fn` fs::existe

```lum
pub fn existe(caminho: str) -> bool { }
```

`true` se o caminho existe.

## `mod` http

```lum
mod http {
```

Módulo `std::http` — cliente HTTP mínimo.

## `struct` http::Resposta

```lum
pub struct Resposta { status: i32, corpo: String }
```

Resposta de uma requisição.

## `fn` http::get

```lum
pub fn get(url: str) -> Result<Resposta, str> { }
```

Faz GET em `url`. `Err` em falha de rede.

## `fn` http::post

```lum
pub fn post(url: str, corpo: str) -> Result<Resposta, str> { }
```

Faz POST de `corpo` em `url`.

## `mod` json

```lum
mod json {
```

Módulo `std::json` — JSON.

## `fn` json::stringify

```lum
pub fn stringify<T>(v: T) -> String { }
```

Serializa `v` para texto JSON.

## `fn` json::parse

```lum
pub fn parse(s: str) -> Result<Json, str> { }
```

Faz parse de `s`. `Err` se o JSON for inválido.

## `enum` json::Json

```lum
pub enum Json { Null, Bool(bool), Num(f64), Str(String), Arr(Vec<Json>), Obj(Map<String, Json>) }
```

Valor JSON dinâmico (`Null | Bool | Num | Str | Arr | Obj`).

## `mod` sqlite

```lum
mod sqlite {
```

Módulo `std::sqlite` — SQLite embarcado.

## `fn` sqlite::abrir

```lum
pub fn abrir(caminho: str) -> Result<Db, str> { }
```

Conexão aberta com `caminho` (`":memory:"` = banco em RAM).

## `struct` sqlite::Db

```lum
pub struct Db { caminho: String }
```

Handle de banco de dados.

## `fn` sqlite::exec

```lum
pub fn exec(db: mut Db, sql: str) -> Result<i32, str> { }
```

Executa SQL sem retorno (CREATE/INSERT/...). Retorna linhas afetadas.

## `fn` sqlite::query

```lum
pub fn query(db: Db, sql: str) -> Result<Vec<Map<String, String>>, str> { }
```

Executa SELECT e devolve linhas como `Vec<Map<String, String>>`.

## `mod` test

```lum
mod test {
```

Módulo `std::test` — asserções para `#[test]`.

## `fn` test::assert

```lum
pub fn assert(cond: bool, msg: str) { }
```

Falha com `msg` se `cond` for `false`.

## `fn` test::assert_eq

```lum
pub fn assert_eq<T>(a: T, b: T) { }
```

Falha se `a != b`.

## `fn` test::assert_ne

```lum
pub fn assert_ne<T>(a: T, b: T) { }
```

Falha se `a == b`.

## `mod` async

```lum
mod async {
```

Módulo `std::async` — concorrência com `async`/`await`.

## `fn` async::spawn

```lum
pub fn spawn<T>(futuro: Future<T>) -> Handle<T> { }
```

Agenda `futuro` para execução concorrente e retorna o handle.

## `fn` async::aguardar

```lum
pub fn aguardar<T>(h: Handle<T>) -> T { }
```

Bloqueia até o handle resolver e devolve o valor.

## `mod` env

```lum
mod env {
```

Módulo `std::env` — ambiente do processo.

## `fn` env::var

```lum
pub fn var(nome: str) -> Option<String> { }
```

Valor da variável `nome`, ou `None`.

## `fn` env::cwd

```lum
pub fn cwd() -> Result<String, str> { }
```

Diretório de trabalho atual.

## `mod` time

```lum
mod time {
```

Módulo `std::time` — relógio.

## `fn` time::agora

```lum
pub fn agora() -> i64 { }
```

Segundos desde o epoch Unix (UTC).

## `fn` time::millis

```lum
pub fn millis() -> i64 { }
```

Milissegundos desde um instante arbitrário (para medir duração).

## `mod` result

```lum
mod result {
```

Módulo `std::result` — `Result<T, E>`, `Option<T>`, `?` e `panic`.

## `struct` result::LumenPanic

```lum
pub struct LumenPanic { msg: String }
```

Erro irrecuperável lançado por `panic`.

## `fn` result::panic

```lum
pub fn panic(msg: str) { }
```

Aborta com erro irrecuperável `msg`.

## `enum` result::Option

```lum
pub enum Option<T> { Some(T), None }
```

`Some(valor)` ou `None` — presença ou ausência de valor.

## `fn` result::is_some

```lum
pub fn is_some<T>(o: Option<T>) -> bool { }
```

`true` se a opção contém valor.

## `fn` result::is_none

```lum
pub fn is_none<T>(o: Option<T>) -> bool { }
```

`true` se a opção está vazia.

## `fn` result::unwrap

```lum
pub fn unwrap<T>(o: Option<T>) -> T { }
```

Desembrulha ou aborta com `panic` em `None`.

## `fn` result::unwrap_or

```lum
pub fn unwrap_or<T>(o: Option<T>, padrao: T) -> T { }
```

Desembrulha ou devolve `padrao`.

## `enum` result::Result

```lum
pub enum Result<T, E> { Ok(T), Err(E) }
```

`Ok(valor)` ou `Err(erro)` — sucesso ou erro recuperável.

## `fn` result::is_ok

```lum
pub fn is_ok<T, E>(r: Result<T, E>) -> bool { }
```

`true` se é `Ok`.

## `fn` result::is_err

```lum
pub fn is_err<T, E>(r: Result<T, E>) -> bool { }
```

`true` se é `Err`.

## `fn` result::q

```lum
pub fn q<T, E>(r: Result<T, E>) -> T { }
```

Operador `?`: desembrulha `Ok` ou propaga `Err` ao chamador.

## `mod` yaml

```lum
mod yaml {
```

Módulo `std::yaml` — YAML (subconjunto: mapas em bloco, sequências
`-`, coleções inline `[a, b]` / `{k: v}`, escalares e `#` comentários).

## `fn` yaml::parse

```lum
pub fn parse(s: str) -> Result<Any, str> { }
```

Faz parse de `s`. Retorna o objeto (`Map`, `Vec`, escalar ou nil).

## `fn` yaml::stringify

```lum
pub fn stringify<T>(v: T) -> String { }
```

Serializa `v` para texto YAML.

## `fn` yaml::read_arquivo

```lum
pub fn read_arquivo(caminho: str) -> Result<Any, str> { }
```

Lê e faz parse do arquivo `caminho`.

## `fn` yaml::write_arquivo

```lum
pub fn write_arquivo<T>(caminho: str, v: T) -> Result<(), str> { }
```

Serializa `v` e escreve no arquivo `caminho`.

## `mod` toml

```lum
mod toml {
```

Módulo `std::toml` — TOML (subconjunto: pares chave/valor, `[table]`,
`[a.b]`, `[[array-table]]`, arrays multilinha, `{k = v}` inline).

## `fn` toml::parse

```lum
pub fn parse(s: str) -> Result<Map<String, Any>, str> { }
```

Faz parse de `s`. Retorna a tabela raiz.

## `fn` toml::stringify

```lum
pub fn stringify(v: Map<String, Any>) -> String { }
```

Serializa a tabela `v` para texto TOML.

## `fn` toml::read_arquivo

```lum
pub fn read_arquivo(caminho: str) -> Result<Map<String, Any>, str> { }
```

Lê e faz parse do arquivo `caminho`.

## `fn` toml::write_arquivo

```lum
pub fn write_arquivo(caminho: str, v: Map<String, Any>) -> Result<(), str> { }
```

Serializa `v` e escreve no arquivo `caminho`.
