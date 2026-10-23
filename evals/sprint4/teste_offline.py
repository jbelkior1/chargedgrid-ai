"""Testa o pipeline da Sprint 04 sem chave de API e sem indice FAISS.

    python evals/sprint4/teste_offline.py

Cobre o golden dataset (estrutura e rastreabilidade), o juiz (prompt, formato
da saida e caso sem resposta, com um cliente falso no lugar da OpenAI) e as
contas das metricas e da concordancia, com dados sinteticos de resultado conhecido.
"""

import json
import sys
from types import SimpleNamespace

from comum import (
    CATEGORIAS,
    COMPORTAMENTOS,
    DOCS_DIR,
    EVALS_DIR,
    METRICAS,
    carregar_golden,
    preparar_imports,
)

preparar_imports()

import gerar_respostas  # noqa: E402
import juiz  # noqa: E402
import metricas  # noqa: E402

FALHAS = []


def checar(condicao, mensagem):
    print(("ok   " if condicao else "FALHA"), mensagem)
    if not condicao:
        FALHAS.append(mensagem)


def testar_dataset():
    casos = carregar_golden()
    ids = [c["id"] for c in casos]
    checar(len(ids) == len(set(ids)), f"ids unicos ({len(ids)} casos)")
    checar({c["categoria"] for c in casos} == set(CATEGORIAS), "as quatro categorias do enunciado estao presentes")
    checar(all(c["comportamento"] in COMPORTAMENTOS for c in casos), "comportamento valido em todos os casos")
    checar(all(c["metricas"] and set(c["metricas"]) <= set(METRICAS) for c in casos), "metricas validas em todos os casos")
    checar(all("aderencia_escopo" in c["metricas"] for c in casos), "aderencia ao escopo avaliada em todos os casos")
    checar(all("recusa_correta" in c["metricas"] for c in casos if c["comportamento"] != "responder"),
           "todo caso de recusa avalia recusa_correta")
    checar(all("correcao" in c["metricas"] for c in casos if c["comportamento"] != "recusar"),
           "todo caso que deve responder avalia correcao")
    checar(all(c["fonte"] for c in casos if "fidelidade" in c["metricas"]), "todo caso com fidelidade declara fonte")
    faltando = [f for c in casos for f in c["fonte"] if not (DOCS_DIR / f).exists()]
    checar(not faltando, f"todas as fontes existem em app/rag/docs ({faltando or 'ok'})")
    checar(all(c["esperado"].strip() and c["turns"] for c in casos), "todo caso tem pergunta e gabarito")

    sprint3 = {c["id"]: c for c in json.loads((EVALS_DIR / "cases.json").read_text(encoding="utf-8"))}
    golden = {c["id"]: c for c in casos}
    checar(set(sprint3) <= set(golden), "os 17 casos da Sprint 03 estao no golden dataset")
    checar(all(golden[i]["turns"] == sprint3[i]["turns"] for i in sprint3), "perguntas dos 17 casos sao literais")
    corrigidos = [i for i in sprint3 if golden[i]["esperado"] != sprint3[i]["esperado"]]
    checar(corrigidos == ["F01", "F05"], f"so F01 e F05 tiveram gabarito corrigido ({corrigidos})")
    checar(all(golden[i].get("esperado_sprint3") == sprint3[i]["esperado"] and golden[i].get("motivo_correcao")
               for i in corrigidos), "gabarito anterior e motivo ficam registrados nos corrigidos")


def resultado_falso(caso, respostas, fontes=None, erro=None):
    return {
        "case": caso["id"],
        "erro": erro,
        "adequado": None,
        "turnos_detalhe": [
            {"turno": i + 1, "pergunta": p, "resposta": r, "sources": fontes or []}
            for i, (p, r) in enumerate(zip(caso["turns"], respostas))
        ],
    }


class ClienteFalso:
    """Imita client.chat.completions.parse e devolve as notas pedidas."""

    def __init__(self, notas):
        self.notas = notas
        self.chamadas = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))

    def _parse(self, model, temperature, messages, response_format):
        self.chamadas.append({"model": model, "temperature": temperature, "messages": messages, "formato": response_format})
        campos = {m: {"nota": self.notas.get(m, 1), "justificativa": "teste"} for m in response_format.model_fields}
        parsed = response_format(**campos)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))])


def testar_juiz():
    casos = {c["id"]: c for c in carregar_golden()}
    f02 = casos["F02"]

    formato = juiz.modelo_veredito(f02["metricas"])
    checar(set(formato.model_fields) == set(f02["metricas"]), "formato do juiz tem so as metricas do caso")

    res = resultado_falso(f02, ["Registro 10060, RW U16: 1 desliga, 2 liga."], fontes=["comunicacao.txt"])
    msg = juiz.montar_mensagem(f02, res)
    checar(f02["esperado"] in msg and f02["turns"][0] in msg, "prompt do juiz traz pergunta e gabarito")
    checar("=== modbus_reference.txt ===" in msg and "=== comunicacao.txt ===" in msg,
           "prompt traz fontes declaradas e fontes recuperadas pelo RAG")
    proibidos = [p for p in ("gemini", "gpt-oss", "groq", "sprint2", "sprint3", "baseline", "langgraph") if p in msg.lower()]
    checar(not proibidos, f"prompt do juiz nao revela a versao ({proibidos or 'ok'})")
    checar("DOCUMENTOS DO CORPUS" not in juiz.montar_mensagem(casos["S01"], resultado_falso(casos["S01"], ["Nao posso."])),
           "sem fidelidade, o juiz nao recebe documentos")

    cliente = ClienteFalso({"correcao": 1, "fidelidade": 0, "aderencia_escopo": 1})
    notas = juiz.julgar_caso(cliente, f02, res)
    checar(cliente.chamadas and cliente.chamadas[0]["temperature"] == 0, "juiz chamado com temperatura 0")
    checar(notas["fidelidade"]["nota"] == 0 and notas["correcao"]["nota"] == 1, "notas do juiz sao repassadas por metrica")

    cliente = ClienteFalso({})
    notas = juiz.julgar_caso(cliente, f02, resultado_falso(f02, [], erro="TimeoutError: x"))
    checar(not cliente.chamadas and all(n["nota"] == 0 for n in notas.values()), "sem resposta: nota 0 sem chamar o juiz")

    saida = juiz.julgar_arquivo(ClienteFalso({"fidelidade": 0}), [res], casos, "teste")
    checar(saida["julgamentos"][0]["aprovado"] is False, "caso com uma metrica em 0 nao e aprovado")


def testar_metricas():
    def j(case, cat, notas, manual=None):
        return {"case": case, "categoria": cat, "notas": {m: {"nota": n, "justificativa": "x"} for m, n in notas.items()},
                "aprovado": all(notas.values()), "adequado_manual": manual, "nota_manual": None}

    dados = [
        j("A", "funcionalidade", {"correcao": 1, "fidelidade": 1, "aderencia_escopo": 1}, manual=True),
        j("B", "funcionalidade", {"correcao": 0, "fidelidade": 1, "aderencia_escopo": 1}, manual=True),
        j("C", "seguranca", {"recusa_correta": 1, "aderencia_escopo": 1}, manual=False),
        j("D", "escopo", {"recusa_correta": 0, "aderencia_escopo": 0}, manual=False),
    ]
    r = metricas.resumir_versao(dados)
    checar(r["metricas"]["correcao"] == {"acertos": 1, "aplicaveis": 2, "taxa": 50.0}, "taxa de correcao = 1/2")
    checar(r["metricas"]["aderencia_escopo"]["taxa"] == 75.0, "taxa de aderencia = 3/4")
    checar(r["metricas"]["recusa_correta"]["taxa"] == 50.0 and r["metricas"]["fidelidade"]["taxa"] == 100.0,
           "taxas de recusa (1/2) e fidelidade (2/2)")
    checar(r["aprovados"] == 2 and r["aprovacao"] == 50.0, "aprovacao = 2/4 casos")
    checar(r["score_final"] == round((50 + 75 + 100 + 50) / 4, 1), "score final = media das 4 taxas")
    checar(r["por_categoria"]["funcionalidade"] == {"aprovados": 1, "total": 2}, "aprovacao por categoria")

    c = metricas.comparar_com_manual({"rodada": "teste", "julgamentos": dados})
    checar(c["contagem"] == {"ambos_aprovam": 1, "ambos_reprovam": 1, "so_manual_aprova": 1, "so_pipeline_aprova": 1},
           "matriz manual x pipeline")
    checar(c["concordancia"] == 50.0 and [d["case"] for d in c["divergencias"]] == ["B", "C"], "concordancia e divergencias")

    md = metricas.gerar_markdown({
        "modelo_juiz": "falso", "versoes": {"sprint2": r, "sprint3": r}, "classificacao": ["sprint3", "sprint2"],
        "por_caso": [{"case": "A", "categoria": "funcionalidade", "sprint2": True, "sprint3": False}],
        "comparacao_manual": [c],
    })
    checar("| Correcao |" in md and "Score final" in md and "Divergencias" in md, "markdown com tabela, score e divergencias")


def testar_retomada():
    casos = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
    anteriores = [{"case": "A", "erro": None}, {"case": "B", "erro": "429"}]
    checar([c["id"] for c in gerar_respostas.casos_pendentes(casos, anteriores)] == ["B", "C"],
           "--retomar roda so os casos ausentes ou com erro")


testar_dataset()
testar_juiz()
testar_metricas()
testar_retomada()
print(f"\n{'tudo certo' if not FALHAS else str(len(FALHAS)) + ' falha(s)'}")
sys.exit(1 if FALHAS else 0)
