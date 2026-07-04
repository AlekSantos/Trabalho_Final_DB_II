"""
executar_teste2_consultas.py — Automatiza o Teste 2 (Seção 8 do enunciado):
mede o tempo de resposta das consultas obrigatórias (por tipo, por período,
geográfica) para os três volumes de dados exigidos.

Para cada volume, este script: (1) recarrega a coleção do zero com aquele
volume de documentos, (2) executa cada consulta várias vezes (para suavizar
ruído de medição) e (3) registra tempo médio, mediana, mínimo e máximo.

Uso:
    python executar_teste2_consultas.py --arquivo dataset/eventos.jsonl
    python executar_teste2_consultas.py --arquivo dataset/eventos.jsonl --repeticoes 30
"""
from __future__ import annotations

import argparse
import csv
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd
import matplotlib.pyplot as plt

import queries
from carga_massa import inserir_em_lotes, ler_eventos
from database import garantir_indices, get_collection

VOLUMES_PADRAO = [1_000, 50_000, 100_000]
REPETICOES_PADRAO = 20

# Parâmetros fixos das consultas de teste — mantidos iguais entre volumes
# para que a comparação de tempo seja justa (mesma "forma" de consulta).
TIPO_TESTE = "Alagamento"
PERIODO_INICIO = datetime(2025, 6, 1)
PERIODO_FIM = datetime(2025, 6, 30, 23, 59, 59)
GEO_LATITUDE = -22.9068  # Centro do Rio de Janeiro
GEO_LONGITUDE = -43.1729
GEO_RAIO_KM = 5


def _medir(func: Callable[[], list], repeticoes: int) -> dict:
    """Executa `func` repetidas vezes e retorna estatísticas de tempo (ms)."""
    tempos_ms = []
    total_resultados = 0
    for _ in range(repeticoes):
        inicio = time.perf_counter()
        resultado = func()
        tempos_ms.append((time.perf_counter() - inicio) * 1000)
        total_resultados = len(resultado)
    return {
        "tempo_medio_ms": round(statistics.mean(tempos_ms), 2),
        "tempo_mediana_ms": round(statistics.median(tempos_ms), 2),
        "tempo_min_ms": round(min(tempos_ms), 2),
        "tempo_max_ms": round(max(tempos_ms), 2),
        "total_resultados": total_resultados,
    }


def _consulta_geografica_com_fallback(colecao):
    try:
        return queries.buscar_por_raio(colecao, GEO_LATITUDE, GEO_LONGITUDE, GEO_RAIO_KM, limite=10_000)
    except Exception:
        return queries.buscar_por_raio_fallback(colecao, GEO_LATITUDE, GEO_LONGITUDE, GEO_RAIO_KM, limite=10_000)


def medir_consultas(colecao, repeticoes: int = REPETICOES_PADRAO) -> list[dict]:
    total_docs = colecao.estimated_document_count()

    consultas = {
        "Por tipo": lambda: queries.listar_por_tipo(colecao, TIPO_TESTE, limite=10_000),
        "Por período": lambda: queries.listar_por_periodo(colecao, PERIODO_INICIO, PERIODO_FIM, limite=10_000),
        "Geográfica (raio)": lambda: _consulta_geografica_com_fallback(colecao),
    }

    resultados = []
    for nome, func in consultas.items():
        print(f"  Medindo '{nome}' ({repeticoes} repetições)...")
        stats = _medir(func, repeticoes)
        stats["consulta"] = nome
        stats["volume_documentos"] = total_docs
        resultados.append(stats)
    return resultados


def executar(
    caminho_arquivo: str, volumes: list[int], repeticoes: int, tamanho_lote: int, saida_csv: str
) -> list[dict]:
    colecao = get_collection()
    todos_resultados = []

    for volume in volumes:
        print(f"\n=== Volume: {volume:,} registros ===".replace(",", "."))
        colecao.drop()
        garantir_indices(colecao)

        eventos = ler_eventos(caminho_arquivo, limite=volume)
        carga = inserir_em_lotes(colecao, eventos, tamanho_lote=tamanho_lote)
        print(
            f"  Carga concluída: {carga.total_inserido:,} documentos em "
            f"{carga.tempo_segundos:.2f}s".replace(",", ".")
        )

        todos_resultados.extend(medir_consultas(colecao, repeticoes))

    _salvar_csv(todos_resultados, saida_csv)
    _gerar_grafico(todos_resultados, str(Path(saida_csv).with_suffix(".png")))
    return todos_resultados


def _salvar_csv(resultados: list[dict], caminho: str) -> None:
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    campos = [
        "volume_documentos",
        "consulta",
        "tempo_medio_ms",
        "tempo_mediana_ms",
        "tempo_min_ms",
        "tempo_max_ms",
        "total_resultados",
    ]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        for r in resultados:
            escritor.writerow({k: r[k] for k in campos})
    print(f"\nResultados salvos em {caminho}")


def _gerar_grafico(resultados: list[dict], caminho: str) -> None:
    df = pd.DataFrame(resultados)
    tabela = df.pivot(index="volume_documentos", columns="consulta", values="tempo_medio_ms").sort_index()

    ax = tabela.plot(kind="bar", figsize=(8, 5))
    ax.set_xlabel("Quantidade de documentos na coleção")
    ax.set_ylabel("Tempo médio de resposta (ms)")
    ax.set_title("Teste 2 — Tempo de resposta das consultas por volume")
    ax.legend(title="Consulta")
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(caminho, dpi=150)
    plt.close()
    print(f"Gráfico salvo em {caminho}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa o Teste 2 (consultas) do trabalho de BD II")
    parser.add_argument("--arquivo", required=True, help="Caminho para o dataset (.jsonl ou .json)")
    parser.add_argument("--volumes", type=int, nargs="+", default=VOLUMES_PADRAO)
    parser.add_argument("--repeticoes", type=int, default=REPETICOES_PADRAO)
    parser.add_argument("--lote", type=int, default=5000)
    parser.add_argument("--saida", default="documentacao/resultados_teste2_consultas.csv")
    args = parser.parse_args()

    resultados = executar(args.arquivo, args.volumes, args.repeticoes, args.lote, args.saida)

    print("\n=== Tabela final (Seção 8, Teste 2) ===")
    print(f"{'Volume':>10} | {'Consulta':<20} | {'Média (ms)':>10} | {'Mediana (ms)':>12}")
    for r in resultados:
        print(
            f"{r['volume_documentos']:>10,} | {r['consulta']:<20} | "
            f"{r['tempo_medio_ms']:>10.2f} | {r['tempo_mediana_ms']:>12.2f}".replace(",", ".")
        )


if __name__ == "__main__":
    main()
