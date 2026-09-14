# Imagem do Lumen v0.1 — implementação de referência em Python 3.12, sem dependências.
#   docker build -f infra/Dockerfile -t lumen:0.1 .
#   docker run --rm lumen:0.1 conformance            # suíte 50/50
#   docker run --rm -v "$PWD:/work" -w /work lumen:0.1 run examples/001_hello.lum
# NOTA: não há binário nativo nesta versão (ver LIMITACOES.md e ROADMAP v0.4);
# o contêiner executa os drivers Python reais (compiler/run.py, lumenc.py, ...).
FROM python:3.12-slim-bookworm
WORKDIR /opt/lumen
COPY . .
ENV PYTHONUNBUFFERED=1
# Smoke de imagem: conformidade 50/50 + exemplos compilam.
RUN python3 conformance/suite.py && python3 tools/test/check_examples.py
COPY infra/docker-entrypoint.py /usr/local/bin/lumen
ENTRYPOINT ["python3", "/usr/local/bin/lumen"]
CMD ["--help"]
