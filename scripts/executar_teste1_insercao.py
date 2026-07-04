"""
executar_teste1_insercao.py — Automatiza o Teste 1 (Seção 8 do enunciado):
mede o tempo de inserção para os volumes exigidos (padrão: 1.000 / 50.000 /
100.000 registros), gera a tabela de resultados em CSV e um gráfico de barras
prontos para colar no Relatório Técnico (Seção 7 - Resultados Experimentais).

Pré-requisito: um arquivo de dataset com pelo menos o maior volume testado,
gerado pelo notebook gerador_dados_sinteticos_eventos_urbanos.ipynb
(dataset/eventos.jsonl é o formato recomendado, por ser lido em streaming
sem carregar o arquivo inteiro em memória de uma vez).

Uso:
    python executar_teste1_insercao.py --arquivo dataset/eventos.jsonl
    python executar_teste1_insercao.py --arquivo dataset/eventos.jsonl --volumes 1000 5000
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt

from carga_massa import inserir_em_lotes, ler_eventos
from database import garantir_indices, get_collection

VOLUMES_PADRAO = [1_000, 50_000, 100_000]


def executar(
    caminho_arquivo: str, volumes: list[int], tamanho_lote: int, saida_csv: str
) -> list[dict]:
    colecao = get_collection()
    resultados = []

    for volume in volumes:
        print(f"\n=== Testando inserção de {volume:,} registros ===".replace(",", "."))
        colecao.drop()  # garante medição limpa, sem sobra de execuções anteriores
        garantir_indices(colecao)

        eventos = ler_eventos(caminho_arquivo, limite=volume)
        if len(eventos) < volume:
            print(
                f"  Aviso: o arquivo só tem {len(eventos):,} registros, "
                f"menos que os {volume:,} solicitados. Gere um dataset maior "
                "no notebook se precisar do volume completo.".replace(",", ".")
            )

        resultado = inserir_em_lotes(colecao, eventos, tamanho_lote=tamanho_lote)
        print(
            f"  {resultado.total_inserido:,} inseridos em {resultado.tempo_segundos:.2f}s "
            f"({resultado.throughput_por_segundo:,.0f} docs/s)".replace(",", ".")
        )

        resultados.append(
            {
                "volume_solicitado": volume,
                "total_inserido": resultado.total_inserido,
                "tempo_segundos": round(resultado.tempo_segundos, 3),
                "throughput_docs_por_segundo": round(resultado.throughput_por_segundo, 1),
                "tamanho_lote": tamanho_lote,
            }
        )

    _salvar_csv(resultados, saida_csv)
    _gerar_grafico(resultados, str(Path(saida_csv).with_suffix(".png")))
    return resultados


def _salvar_csv(resultados: list[dict], caminho: str) -> None:
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(resultados[0].keys()))
        escritor.writeheader()
        escritor.writerows(resultados)
    print(f"\nResultados salvos em {caminho}")


def _gerar_grafico(resultados: list[dict], caminho: str) -> None:
    volumes = [r["volume_solicitado"] for r in resultados]
    tempos = [r["tempo_segundos"] for r in resultados]

    plt.figure(figsize=(7, 4))
    plt.bar([str(v) for v in volumes], tempos, color="#3b6fa0")
    plt.xlabel("Quantidade de registros")
    plt.ylabel("Tempo de inserção (s)")
    plt.title("Teste 1 — Tempo de inserção por volume")
    plt.tight_layout()
    plt.savefig(caminho, dpi=150)
    plt.close()
    print(f"Gráfico salvo em {caminho}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa o Teste 1 (inserção) do trabalho de BD II")
    parser.add_argument("--arquivo", required=True, help="Caminho para o dataset (.jsonl ou .json)")
    parser.add_argument(
        "--volumes",
        type=int,
        nargs="+",
        default=VOLUMES_PADRAO,
        help="Volumes a testar (padrão: 1000 50000 100000)",
    )
    parser.add_argument("--lote", type=int, default=5000, help="Tamanho do lote de insert_many")
    parser.add_argument("--saida", default="documentacao/resultados_teste1_insercao.csv")
    args = parser.parse_args()

    resultados = executar(args.arquivo, args.volumes, args.lote, args.saida)

    print("\n=== Tabela final (Seção 8, Teste 1) ===")
    print(f"{'Volume':>12} | {'Tempo (s)':>10} | {'Docs/s':>10}")
    for r in resultados:
        print(
            f"{r['volume_solicitado']:>12,} | {r['tempo_segundos']:>10.2f} | "
            f"{r['throughput_docs_por_segundo']:>10,.0f}".replace(",", ".")
        )


if __name__ == "__main__":
    main()
