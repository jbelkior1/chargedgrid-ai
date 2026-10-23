"""Caminhos e definicoes compartilhados pelo pipeline de avaliacao da Sprint 04.

O pipeline reaproveita os harnesses da Sprint 03 (evals/run.py e
evals/run_legacy.py) para gerar as respostas, e acrescenta o juiz e as metricas.
Nada aqui altera os arquivos da Sprint 03 nem os resultados dela.
"""

import json
import sys
from pathlib import Path

SPRINT4_DIR = Path(__file__).resolve().parent
EVALS_DIR = SPRINT4_DIR.parent
BASE_DIR = EVALS_DIR.parent
DOCS_DIR = BASE_DIR / "app" / "rag" / "docs"
GOLDEN_PATH = SPRINT4_DIR / "golden_dataset.json"
RESULTADOS_DIR = SPRINT4_DIR / "results"
SPRINT3_RESULTS_DIR = EVALS_DIR / "results"

CATEGORIAS = ("funcionalidade", "escopo", "seguranca", "borda")
COMPORTAMENTOS = ("responder", "recusar", "responder_e_recusar")

# As quatro metricas pedidas no enunciado da Sprint 04, na ordem do relatorio.
METRICAS = ("correcao", "aderencia_escopo", "fidelidade", "recusa_correta")
NOMES_METRICAS = {
    "correcao": "Correcao",
    "aderencia_escopo": "Aderencia ao escopo GoodWe",
    "fidelidade": "Fidelidade ao contexto",
    "recusa_correta": "Recusa correta",
}

# As duas versoes comparadas. O modelo de cada uma e o mesmo que a Sprint 03
# mediu, para que a comparacao com a avaliacao manual faca sentido.
VERSOES = {
    "sprint2": {
        "nome": "Sprint 2 - ask_ai + RAG + memoria manual",
        "alvo": "baseline",
        "modelo": "groq/openai/gpt-oss-20b",
        "arquivo_sprint3": "baseline_sprint2.json",
    },
    "sprint3": {
        "nome": "Sprint 3 - agente LangGraph + memoria por sessao",
        "alvo": "agente",
        "modelo": "google/gemini-3.6-flash",
        "temperatura": 0.1,
        "arquivo_sprint3": "agent_google_gemini_3_6_flash.json",
    },
}


def preparar_imports():
    """Deixa `app`, `agent_core` e os harnesses de evals/ importaveis."""
    for caminho in (str(BASE_DIR), str(EVALS_DIR)):
        if caminho not in sys.path:
            sys.path.insert(0, caminho)


def carregar_golden():
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def ler_json(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def gravar_json(caminho, dados):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Gravado: {caminho}")


def texto_documento(nome):
    """Conteudo de um documento do corpus do RAG (app/rag/docs)."""
    return (DOCS_DIR / nome).read_text(encoding="utf-8")
