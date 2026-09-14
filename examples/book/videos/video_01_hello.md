# Vídeo 01 — Hello, Lumen em 10 minutos

> Público: nunca viu Lumen. Meta: sair com toolchain instalada e
> primeiro programa rodando. Arquivo: `examples/001_hello.lum`.

## 0:00–1:30 — Abertura

- [FALA] "Lumen é uma linguagem pequena, estática e com `match`
  exaustivo — e hoje você roda seu primeiro programa."
- [TELA] logo + `lumen --version` no terminal.

## 1:30–4:00 — Instalação (rápido, sem travar)

- [TELA] `git clone` + build ou `docker build -f infra/Dockerfile`.
- [FALA] "Três alvos: VM, C e WASM — o padrão é VM."
- Mostra `lumen run / lumen build / lumen test` no `--help`.

## 4:00–7:30 — O hello, linha a linha

- [TELA] abre `001_hello.lum`:
  ```lum
  fn main() {
      println("Olá, Lumen!");
  }
  ```
- [FALA] "`fn main` é a porta de entrada; `println` pula linha;
  tudo termina com `;`."
- [TELA] roda; quebra o `;` de propósito e lê o erro junto.

## 7:30–9:30 — Compile para 3 alvos

- [TELA] `lumen build --target vm|c|wasm` + executa cada saída.
- [FALA] "Mesmo fonte, três backends — a suíte `BE-*` garante."

## 9:30–10:00 — Encerramento + CTA

- [FALA] "Na descrição: tutorial 01, `002_fatorial` e o próximo
  vídeo, sobre `match`. Se inscreve e bora."
- [TELA] comandos do vídeo colados na descrição.
