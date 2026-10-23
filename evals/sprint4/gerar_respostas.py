"""Roda o golden dataset contra uma versao do chatbot e grava as respostas.

    python evals/sprint4/gerar_respostas.py --versao sprint2
    python evals/sprint4/gerar_respostas.py --versao sprint3
    python evals/sprint4/gerar_respostas.py --versao sprint2 --retomar   # so os casos que faltam

A execucao de cada caso e a MESMA da Sprint 03: `run_case` de evals/run.py
(agente) e de evals/run_legacy.py (baseline). Este script so troca a lista de
casos pelo golden dataset e grava em evals/sprint4/results/, sem sobrescrever
os resultados da Sprint 03.

--retomar existe por causa da cota diaria da Groq (200.000 tokens por modelo):
se a rodada parar no meio, a proxima continua dos casos que faltaram ou deram
erro, sem repetir os que ja tem resposta.
"""

import argparse
import asyncio

from comum import RESULTADOS_DIR, VERSOES, carregar_golden, gravar_json, ler_json, preparar_imports

preparar_imports()


def caminho_respostas(versao):
    return RESULTADOS_DIR / f"respostas_{versao}.json"


def casos_pendentes(casos, anteriores):
    """Casos sem resposta valida na rodada anterior (ausentes ou com erro)."""
    feitos = {r["case"] for r in anteriores if not r.get("erro")}
    return [c for c in casos if c["id"] not in feitos]


def rodar_agente(config, casos):
    import run as run_agente
    from agent_core.config import build_chat_model, build_router_model
    from agent_core.graph import build_graph

    provider, model_id = run_agente.parse_model(config["modelo"])
    chat_model = build_chat_model(provider=provider, model_id=model_id, temperature=config["temperatura"])
    router_model = build_router_model(provider=provider, model_id=model_id)
    graph = build_graph(chat_model=chat_model, router_model=router_model)
    sleep = run_agente.DEFAULT_SLEEP.get(provider, 1.0)

    resultados = []
    for caso in casos:
        print(f"  [{caso['id']}] {caso['categoria']}")
        resultados.append(run_agente.run_case(graph, caso, config["modelo"], sleep))
    return resultados


async def rodar_baseline(config, casos):
    import run_legacy
    from app import database

    model_id = config["modelo"].split("/", 1)[1]
    run_legacy.patch_baseline_model(model_id)
    database.init_db()
    model_name = f"baseline-sprint2/ask_ai+{model_id}"

    resultados = []
    for caso in casos:
        print(f"  [{caso['id']}] {caso['categoria']}")
        resultados.append(await run_legacy.run_case(caso, model_name))
    return resultados


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versao", required=True, choices=sorted(VERSOES))
    parser.add_argument("--retomar", action="store_true", help="roda so os casos ausentes ou com erro")
    args = parser.parse_args()

    config = VERSOES[args.versao]
    casos = carregar_golden()
    destino = caminho_respostas(args.versao)

    anteriores = []
    if args.retomar and destino.exists():
        anteriores = ler_json(destino)["resultados"]
        casos = casos_pendentes(casos, anteriores)

    print(f"{'=' * 68}\nVERSAO {args.versao}: {config['nome']} ({config['modelo']})\n{'=' * 68}")
    print(f"{len(casos)} casos a rodar")

    if config["alvo"] == "agente":
        novos = rodar_agente(config, casos)
    else:
        novos = asyncio.run(rodar_baseline(config, casos))

    # Junta com a rodada anterior mantendo a ordem do golden dataset.
    por_caso = {r["case"]: r for r in anteriores}
    por_caso.update({r["case"]: r for r in novos})
    ordem = [c["id"] for c in carregar_golden()]
    resultados = [por_caso[cid] for cid in ordem if cid in por_caso]

    gravar_json(destino, {
        "versao": args.versao,
        "nome": config["nome"],
        "alvo": config["alvo"],
        "modelo": config["modelo"],
        "temperatura": config.get("temperatura"),
        "total_casos": len(resultados),
        "casos_com_erro": [r["case"] for r in resultados if r.get("erro")],
        "resultados": resultados,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
