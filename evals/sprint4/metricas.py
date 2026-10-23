"""Calcula as metricas a partir dos julgamentos e gera results/resultados.md.

    python evals/sprint4/metricas.py

Nenhum numero e digitado a mao: tudo sai dos JSONs de evals/sprint4/results/.

Como cada numero e calculado:
- taxa da metrica = casos com nota 1 / casos em que a metrica se aplica;
- aprovacao = casos aprovados / total de casos, e um caso e aprovado quando
  todas as metricas que se aplicam a ele tem nota 1;
- score final = media simples das quatro taxas de metrica;
- concordancia com a Sprint 03 = casos em que o veredito humano (`adequado`) e o
  do pipeline (`aprovado`) coincidem / casos com veredito humano.
"""

import sys

from comum import METRICAS, NOMES_METRICAS, RESULTADOS_DIR, VERSOES, CATEGORIAS, gravar_json, ler_json


def pct(parte, total):
    return round(100 * parte / total, 1) if total else None


def fmt(valor):
    return "-" if valor is None else f"{valor:.1f}%"


def resumir_versao(julgamentos):
    metricas = {}
    for m in METRICAS:
        notas = [j["notas"][m]["nota"] for j in julgamentos if m in j["notas"]]
        metricas[m] = {"acertos": sum(notas), "aplicaveis": len(notas), "taxa": pct(sum(notas), len(notas))}

    taxas = [v["taxa"] for v in metricas.values() if v["taxa"] is not None]
    aprovados = sum(j["aprovado"] for j in julgamentos)

    por_categoria = {}
    for cat in CATEGORIAS:
        doc = [j for j in julgamentos if j["categoria"] == cat]
        por_categoria[cat] = {"aprovados": sum(j["aprovado"] for j in doc), "total": len(doc)}

    return {
        "metricas": metricas,
        "aprovados": aprovados,
        "total": len(julgamentos),
        "aprovacao": pct(aprovados, len(julgamentos)),
        "score_final": round(sum(taxas) / len(taxas), 1) if taxas else None,
        "por_categoria": por_categoria,
    }


def comparar_com_manual(julgamento):
    """Veredito humano da Sprint 03 x veredito do pipeline, caso a caso."""
    pares = [j for j in julgamento["julgamentos"] if j["adequado_manual"] is not None]
    contagem = {"ambos_aprovam": 0, "ambos_reprovam": 0, "so_manual_aprova": 0, "so_pipeline_aprova": 0}
    divergencias = []
    for j in pares:
        manual, auto = bool(j["adequado_manual"]), bool(j["aprovado"])
        if manual and auto:
            contagem["ambos_aprovam"] += 1
        elif not manual and not auto:
            contagem["ambos_reprovam"] += 1
        elif manual:
            contagem["so_manual_aprova"] += 1
        else:
            contagem["so_pipeline_aprova"] += 1
        if manual != auto:
            reprovadas = {m: n["justificativa"] for m, n in j["notas"].items() if n["nota"] == 0}
            divergencias.append({
                "case": j["case"],
                "manual": "adequado" if manual else "inadequado",
                "pipeline": "aprovado" if auto else "reprovado",
                "metricas_reprovadas": reprovadas,
                "nota_manual": j.get("nota_manual"),
            })
    concordam = contagem["ambos_aprovam"] + contagem["ambos_reprovam"]
    return {
        "rodada": julgamento.get("rodada"),
        "casos": len(pares),
        "acertos_manual": sum(bool(j["adequado_manual"]) for j in pares),
        "aprovados_pipeline": sum(bool(j["aprovado"]) for j in pares),
        "concordancia": pct(concordam, len(pares)),
        "contagem": contagem,
        "divergencias": divergencias,
    }


def gerar_markdown(resumo):
    v = resumo["versoes"]
    nomes = list(v)
    L = ["# Resultados do pipeline de avaliacao - Sprint 04", "",
         "Gerado por `python evals/sprint4/metricas.py` a partir dos JSONs de `evals/sprint4/results/`. "
         "Nenhum numero desta pagina foi digitado a mao.", "",
         f"- Juiz: `{resumo['modelo_juiz']}`, temperatura 0, sem saber qual versao respondeu.",
         f"- Golden dataset: {v[nomes[0]]['total']} casos.", ""]

    L += ["## 1. Resultado por versao e por metrica", "",
          "| Metrica | " + " | ".join(f"{n} ({VERSOES[n]['modelo']})" for n in nomes) + " |",
          "|---|" + "---|" * len(nomes)]
    for m in METRICAS:
        celulas = [f"{fmt(v[n]['metricas'][m]['taxa'])} ({v[n]['metricas'][m]['acertos']}/{v[n]['metricas'][m]['aplicaveis']})" for n in nomes]
        L.append(f"| {NOMES_METRICAS[m]} | " + " | ".join(celulas) + " |")
    L.append("| **Aprovacao (casos com todas as metricas em 1)** | " + " | ".join(
        f"**{fmt(v[n]['aprovacao'])}** ({v[n]['aprovados']}/{v[n]['total']})" for n in nomes) + " |")
    L.append("| **Score final (media das 4 metricas)** | " + " | ".join(f"**{fmt(v[n]['score_final'])}**" for n in nomes) + " |")

    L += ["", "## 2. Classificacao", ""]
    for i, n in enumerate(resumo["classificacao"], 1):
        L.append(f"{i}. **{n}** - score final {fmt(v[n]['score_final'])}, aprovacao {fmt(v[n]['aprovacao'])}")

    L += ["", "## 3. Aprovacao por categoria", "", "| Categoria | " + " | ".join(nomes) + " |", "|---|" + "---|" * len(nomes)]
    for cat in CATEGORIAS:
        L.append(f"| {cat} | " + " | ".join(
            f"{v[n]['por_categoria'][cat]['aprovados']}/{v[n]['por_categoria'][cat]['total']}" for n in nomes) + " |")

    L += ["", "## 4. Veredito por caso", "", "| Caso | Categoria | " + " | ".join(nomes) + " |", "|---|---|" + "---|" * len(nomes)]
    for linha in resumo["por_caso"]:
        L.append(f"| {linha['case']} | {linha['categoria']} | " + " | ".join(
            "ok" if linha[n] else "reprovado" for n in nomes) + " |")

    manual = resumo.get("comparacao_manual") or []
    if manual:
        L += ["", "## 5. Pipeline x avaliacao manual da Sprint 03", "",
              "Mesmas respostas que a Sprint 03 julgou a mao, agora julgadas pelo pipeline.", "",
              "| Rodada da Sprint 03 | Casos | Acertos (manual) | Aprovados (pipeline) | Concordancia | So o manual aprova | So o pipeline aprova |",
              "|---|---|---|---|---|---|---|"]
        for c in manual:
            L.append(f"| `{c['rodada']}` | {c['casos']} | {c['acertos_manual']} | {c['aprovados_pipeline']} | "
                     f"{fmt(c['concordancia'])} | {c['contagem']['so_manual_aprova']} | {c['contagem']['so_pipeline_aprova']} |")
        L += ["", "### Divergencias", ""]
        for c in manual:
            for d in c["divergencias"]:
                L.append(f"- `{c['rodada']}` **{d['case']}**: manual {d['manual']}, pipeline {d['pipeline']}.")
                for m, just in d["metricas_reprovadas"].items():
                    L.append(f"  - juiz, {m} = 0: {just}")
                if d["nota_manual"]:
                    L.append(f"  - nota manual: {d['nota_manual']}")
    return "\n".join(L) + "\n"


def main():
    julgamentos = {}
    for nome in VERSOES:
        arquivo = RESULTADOS_DIR / f"julgamento_{nome}.json"
        if not arquivo.exists():
            print(f"Falta {arquivo.name}: rode evals/sprint4/juiz.py --versao {nome}")
            return 1
        julgamentos[nome] = ler_json(arquivo)

    versoes = {n: resumir_versao(j["julgamentos"]) for n, j in julgamentos.items()}
    classificacao = sorted(versoes, key=lambda n: (versoes[n]["score_final"] or 0, versoes[n]["aprovacao"] or 0), reverse=True)

    por_caso = []
    for j in julgamentos[next(iter(julgamentos))]["julgamentos"]:
        linha = {"case": j["case"], "categoria": j["categoria"]}
        for n, dados in julgamentos.items():
            linha[n] = next(x["aprovado"] for x in dados["julgamentos"] if x["case"] == j["case"])
        por_caso.append(linha)

    comparacao = [comparar_com_manual(ler_json(a)) for a in sorted(RESULTADOS_DIR.glob("julgamento_manual_*.json"))]

    resumo = {
        "modelo_juiz": julgamentos[next(iter(julgamentos))]["modelo_juiz"],
        "versoes": versoes,
        "classificacao": classificacao,
        "por_caso": por_caso,
        "comparacao_manual": comparacao,
    }
    gravar_json(RESULTADOS_DIR / "resumo.json", resumo)
    (RESULTADOS_DIR / "resultados.md").write_text(gerar_markdown(resumo), encoding="utf-8")
    print(f"Gravado: {RESULTADOS_DIR / 'resultados.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
