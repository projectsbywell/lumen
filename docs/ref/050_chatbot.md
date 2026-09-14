# `examples/001-050/050_chatbot.lum`

50 — Chatbot com `match` de padrões e strings.

O chatbot reconhece intenções do usuário através de
`match` em padrões de string e responde adequadamente.
Usa `for`, `if-else` e `Result` para fluxo de conversa.

## Índice

- `enum` [Intencao](#intencao)
- `fn` [reconhecer](#reconhecer)
- `fn` [responder](#responder)
- `fn` [processar](#processar)
- `fn` [sessao](#sessao)
- `fn` [main](#main)
- `fn` [testa_chatbot](#testa-chatbot)

## `enum` Intencao

```lum
enum Intencao {
```

Intenção reconhecida pelo chatbot.

## `fn` reconhecer

```lum
fn reconhecer(texto: str) -> Intencao {
```

Reconhece a intenção a partir do texto de entrada.

## `fn` responder

```lum
fn responder(intencao: Intencao) -> str {
```

Gera resposta baseada na intenção reconhecida.

## `fn` processar

```lum
fn processar(frase: str) -> str {
```

Processa uma frase inteira: reconhece e responde.

## `fn` sessao

```lum
fn sessao(mensagens: Vec<str>) -> Vec<str> {
```

Executa uma sessão de chat com múltiplas mensagens.

## `fn` main

```lum
fn main() {
```

Ponto de entrada do programa.

## `fn` testa_chatbot

```lum
fn testa_chatbot() {
```

Atributos: `#[test]`

_Sem documentação `///`._
