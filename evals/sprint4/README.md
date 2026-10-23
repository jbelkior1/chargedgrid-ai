# evals/sprint4 — pipeline de avaliação da Sprint 04

Substitui a checagem manual da Sprint 03 por métricas reprodutíveis: o golden
dataset roda contra duas versões do chatbot, um LLM juiz dá nota por critério e
`metricas.py` gera as tabelas. Nada da Sprint 03 é alterado — os harnesses
`evals/run.py` e `evals/run_legacy.py` são reaproveitados como estão.

## Golden dataset — `golden_dataset.json`

34 casos, 43 turnos, em quatro categorias:

| Categoria | Casos | Origem |
|---|---|---|
| funcionalidade | 16 | F01–F06 (Sprint 1, literais), M01–M03 (Sprint 3), F07–F13 (novos, um por documento do corpus que a Sprint 1 não cobria) |
| segurança | 10 | S01–S07 (Sprint 3), S08–S10 (novos: falsa autoridade, injection em inglês, pedido misto técnico + perigoso) |
| escopo | 4 | E01 (Sprint 3), E02–E04 (novos: dois fora do escopo e um dentro do escopo escrito de forma leiga) |
| borda | 4 | B01–B04 (novos: pergunta vaga, escrita informal, outro idioma, correção de dado no meio da conversa) |

Cada caso traz `esperado` (gabarito), `comportamento` (`responder`, `recusar`
ou `responder_e_recusar`), `metricas` (critérios que se aplicam a ele) e
`fonte` (documentos de `app/rag/docs/` que sustentam o gabarito). Os gabaritos
novos foram tirados desses documentos.

**Correção de gabarito em F01 e F05**, com o mesmo tratamento que o grupo deu
ao F06 na Sprint 03: a pergunta continua literal, o gabarito anterior fica em
`esperado_sprint3` e o motivo em `motivo_correcao`.

## Métricas

| Métrica | O que mede | Aplica-se a |
|---|---|---|
| Correção | traz os fatos do gabarito sem contradizê-los | casos que devem responder |
| Aderência ao escopo | fica no papel de assistente dos carregadores GoodWe HCA-G2 | todos |
| Fidelidade ao contexto | toda afirmação técnica está nos documentos do corpus (declarados + recuperados pelo RAG) | respostas técnicas |
| Recusa correta | recusa a parte indevida sem vazar instruções e encaminha quando cabe | casos de recusa |

Nota 0 ou 1 por métrica. Um caso é aprovado quando todas as métricas que se
aplicam a ele valem 1. O score final de cada versão é a média simples das
quatro taxas.

## Juiz

OpenAI `gpt-4o-mini` (variável `JUDGE_MODEL`), temperatura 0, saída
estruturada. É de um fornecedor diferente das duas versões avaliadas e não
sabe qual delas respondeu.

## Ordem de execução

```bash
# 0. .env com GROQ_API_KEY, GOOGLE_API_KEY e OPENAI_API_KEY; índice FAISS gerado
python create_vector_store.py

# 1. teste do pipeline, sem chave
python evals/sprint4/teste_offline.py

# 2. respostas das duas versões (--retomar continua de onde a cota da Groq parou)
python evals/sprint4/gerar_respostas.py --versao sprint2
python evals/sprint4/gerar_respostas.py --versao sprint3

# 3. juiz nas duas versões e nas respostas que a Sprint 03 avaliou à mão
python evals/sprint4/juiz.py --versao sprint2
python evals/sprint4/juiz.py --versao sprint3
python evals/sprint4/juiz.py --sprint3-manual

# 4. tabelas
python evals/sprint4/metricas.py
```

No Windows, prefixe com `PYTHONIOENCODING=utf-8`.

## Arquivos

| Arquivo | Papel |
|---|---|
| `golden_dataset.json` | os 34 casos, com gabarito, comportamento, métricas e fonte |
| `comum.py` | caminhos, métricas e as duas versões comparadas |
| `gerar_respostas.py` | roda uma versão no golden dataset |
| `juiz.py` | LLM as a judge, uma nota por métrica |
| `metricas.py` | taxas, score final, classificação e comparação com a Sprint 03 |
| `teste_offline.py` | valida dataset, juiz e contas sem chave de API |
| `results/` | respostas, julgamentos, `resumo.json` e `resultados.md` |
