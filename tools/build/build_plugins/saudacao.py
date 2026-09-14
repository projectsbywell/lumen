# -*- coding: utf-8 -*-
"""Plugin de exemplo do sistema de build do Lumen.

Hooks opcionais (todos recebem `ctx` — lumen_build.BuildContext):
    before_build(ctx)                       antes do build
    before_task(ctx, task)                  antes de cada tarefa
    after_task(ctx, task, status)           depois de cada tarefa
        status: 'executed' | 'skipped' | 'dry-run' | 'failed-ignored'
    after_build(ctx)                        ao final
    register_tasks(ctx) -> [ {nome: spec} ] tarefas extras
"""


def before_build(ctx):
    print("[plugin:saudacao] build iniciado no projeto "
          f"{ctx.project_dir.name}")


def after_task(ctx, task, status):
    print(f"[plugin:saudacao] tarefa finalizada: {status}")


def register_tasks(ctx):
    return [{
        "verificacao": {
            "cmd": "python3 ferramentas/limpar.py --check",
            "desc": "verificação extra registrada pelo plugin",
            "deps": ["empacotar"],
        }
    }]


def after_build(ctx):
    print(f"[plugin:saudacao] fim do build: {len(ctx.results)} tarefa(s)")