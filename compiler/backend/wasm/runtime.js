/* Runtime JS do Lumen (WASM): instancia .wasm compilado do WAT.
 *
 * Imports esperados pelo módulo:
 *   lumen.print(i32) — imprime um inteiro (capturável p/ testes).
 * Exports do módulo:
 *   mem  — memória linear (i32 / strings futuras);
 *   <fn> — uma função exportada por função Lumen ((params i32) (result i32)).
 *
 * Uso (Node ≥ 18):
 *   import { instanciarLumen, executarMain } from "./runtime.js";
 *   const mod = await instanciarLumen(bytes);
 *   console.log(executarMain(mod)); // => valor de main() + prints em mod.prints
 *
 * Uso (navegador / Wasmtime):
 *   Wasmtime já resolve `lumen.print` via Linker; este arquivo é o
 *   equivalente JS dessa ponte, com o mesmo comportamento observável.
 */

export async function instanciarLumen(bytes, onPrint) {
  const prints = [];
  const imports = {
    lumen: { print: (x) => { prints.push(x); (onPrint ?? defaultPrint)(x); } },
  };
  const { instance } = await WebAssembly.instantiate(bytes, imports);
  return { exports: instance.exports, mem: instance.exports.mem ?? null, prints };
}

export function executarMain(mod, args = []) {
  if (typeof mod.exports.main !== "function") {
    throw new Error("módulo sem export 'main'");
  }
  return { retorno: mod.exports.main(...args), prints: mod.prints };
}

export function chamar(mod, nome, args = []) {
  const fn = mod.exports[nome];
  if (typeof fn !== "function") throw new Error(`export '${nome}' não encontrado`);
  return fn(...args);
}

function defaultPrint(x) {
  console.log("lumen>", x);
}
