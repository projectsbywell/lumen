# Tutorial 01 — Instalação e Hello (~20 min)

> Nível 0. Ao final: toolchain instalada, primeiro programa rodando,
> `lumen run/build/test/doc` conhecidos.

## 1. Instalar

```sh
# via script (linux/macos) ou Docker (ver infra/Dockerfile)
git clone <repo-lumen> && cd lumen
cargo build --release   # ou: docker build -f infra/Dockerfile -t lumen .
lumen --version         # → lumen 0.1.0
```

## 2. Hello

Crie `ola.lum` (ou use `examples/001_hello.lum`):

```lum
/// Meu primeiro programa.
fn main() {
    println("Olá, Lumen!");
}
```

```sh
lumen run ola.lum
# → Olá, Lumen!
```

Três regras que já apareceram:

1. `fn main() { }` é a porta de entrada — todo programa tem uma; é por
   ela que a execução começa.
2. `println` imprime com quebra de linha no final (`\n` = "nova linha";
   `print` não pula linha).
3. Toda instrução termina com `;` e o arquivo termina com uma quebra de
   linha (aperte Enter na última linha).

## 3. Compilar e testar

```sh
# "build" = gerar o programa final. Sem --target, roda na VM (máquina
# virtual do Lumen). Com --target c/wasm, gera código C ou WebAssembly.
lumen build ola.lum -o ola        # padrão: vm
lumen build --target c ola.lum    # backend C
lumen build --target wasm ola.lum # backend WASM (roda no navegador)
lumen test                        # roda as funções marcadas com #[test]
lumen fmt                         # formata o código (ver docs/STYLE.md)
lumen doc                         # gera docs via docs/gen.py
```

## 4. Exercícios

1. Imprima seu nome com `print` (sem `\n`) + `println`.
2. Quebre de propósito: tire o `;` e leia o erro do compilador.
3. Rode `python3 conformance/suite.py --filter runtime` e veja os
   casos `RT-*` — são estes programas, como teste executável.

Próximo: `02_funcoes_tipos.md`.
