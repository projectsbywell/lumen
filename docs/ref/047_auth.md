# `examples/001-050/047_auth.lum`

047 — Sistema de autenticação com `Result`, `Option` e `match`.

Login valida credenciais, tokens são `Option`, e sessões
são gerenciadas com `Result` para erros recuperáveis.

## Índice

- `enum` [Papel](#papel)
- `enum` [AuthResult](#authresult)
- `struct` [Usuario](#usuario)
- `fn` [login](#login)
- `fn` [gerar_token](#gerar-token)
- `fn` [verificar_token](#verificar-token)
- `fn` [main](#main)
- `fn` [testa_auth](#testa-auth)

## `enum` Papel

```lum
enum Papel {
```

Papel do usuário no sistema.

## `enum` AuthResult

```lum
enum AuthResult {
```

Resultado de uma tentativa de login.

## `struct` Usuario

```lum
struct Usuario {
```

Usuário registrado.

## `fn` login

```lum
fn login(usuario: Usuario, senha: str) -> AuthResult {
```

Verifica credenciais e retorna `AuthResult`.

## `fn` gerar_token

```lum
fn gerar_token(usuario: Usuario, papel: Papel) -> Option<str> {
```

Gera token opcional para sessão; `None` se falhar.

## `fn` verificar_token

```lum
fn verificar_token(token: Option<str>) -> Result<str, str> {
```

Verifica se o token é válido; retorna `Result`.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_auth

```lum
fn testa_auth() {
```

Atributos: `#[test]`

_Sem documentação `///`._
