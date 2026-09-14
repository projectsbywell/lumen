# 20 — Publicando seu pacote

Do `lumen.toml` ao registry local em 5 comandos:

```sh
# 1. inicia o projeto
python3 tools/pkg/lumen_pkg.py new meuapp
cd meuapp

# 2. declara e trava dependências
python3 ../tools/pkg/lumen_pkg.py add demo-pkg@'*'
python3 ../tools/pkg/lumen_pkg.py install

# 3. sobe o registry (outro terminal / outro Termux)
LUMEN_REGISTRY=http://127.0.0.1:8765 python3 ../tools/pkg/registry.py --port 8765

# 4. empacota e publica
python3 ../tools/pkg/lumen_pkg.py pack
python3 ../tools/pkg/lumen_pkg.py publish --registry http://127.0.0.1:8765

# 5. verifica a assinatura
python3 ../tools/pkg/lumen_pkg.py verify meuapp-0.1.0.lumepkg
```

O "registry" é o servidor onde o pacote fica guardado; "publicar" é
enviar para lá. A assinatura prova quem criou o pacote: sem a variável
`LUMEN_HMAC_KEY` (senha da assinatura) ela é de mentira ("demo", não use
em produção — ver `LIMITACOES.md` item 4). Com a chave exportada
(`export LUMEN_HMAC_KEY=...`), o `verify` confere de verdade. A lista de
pacotes sai em `GET /index` (endereço `/index` no servidor).
