"""
carga_massa.py — Carga em massa dos eventos sintéticos no MongoDB, com medição
de tempo de inserção.
BD II - IC/UFRJ — dá suporte ao Teste 1 (Seção 8 do enunciado)

Uso via linha de comando:
    python carga_massa.py --arquivo dataset/eventos.jsonl --lote 5000
    python carga_massa.py --arquivo dataset/eventos.jsonl --limite 1000 --recriar
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pymongo.collection import Collection
from pymongo.errors import BulkWriteError

from database import garantir_indices, get_collection


@dataclass
class ResultadoCarga:
    total_lido: int
    total_inserido: int
    tempo_segundos: float
    tamanho_lote: int

    @property
    def throughput_por_segundo(self) -> float:
        return self.total_inserido / self.tempo_segundos if self.tempo_segundos else 0.0


def _converter_para_documento(evento_dict: dict) -> dict:
    """Converte um evento lido do arquivo (dataHora como string ISO) para o
    formato final gravado no Mongo: dataHora como datetime nativo + campo
    geoespacial 'location' (GeoJSON) derivado de 'localizacao'.

    Não passa pelo Pydantic (models.Evento) de propósito: para um experimento
    de performance de carga de dados sintéticos já confiáveis, a validação
    campo a campo adicionaria um overhead de CPU que mascararia o que
    realmente queremos medir aqui — o tempo de inserção no banco.
    """
    doc = dict(evento_dict)
    if isinstance(doc["dataHora"], str):
        doc["dataHora"] = datetime.fromisoformat(doc["dataHora"])
    lat = doc["localizacao"]["latitude"]
    lon = doc["localizacao"]["longitude"]
    doc["location"] = {"type": "Point", "coordinates": [lon, lat]}
    return doc


def ler_eventos(caminho: str | Path, limite: int | None = None) -> list[dict]:
    """Lê eventos de um arquivo .json (array) ou .jsonl (um objeto por linha),
    exportado pelo notebook gerador_dados_sinteticos_eventos_urbanos.ipynb,
    já convertidos para o formato pronto para inserção no Mongo.
    """
    caminho = Path(caminho)
    eventos: list[dict] = []

    if caminho.suffix == ".jsonl":
        with caminho.open("r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                eventos.append(_converter_para_documento(json.loads(linha)))
                if limite and len(eventos) >= limite:
                    break
    else:
        with caminho.open("r", encoding="utf-8") as f:
            bruto = json.load(f)
        if limite:
            bruto = bruto[:limite]
        eventos = [_converter_para_documento(e) for e in bruto]

    return eventos


def inserir_em_lotes(
    colecao: Collection, eventos: list[dict], tamanho_lote: int = 5000
) -> ResultadoCarga:
    """Insere os eventos em lotes de `tamanho_lote` usando insert_many com
    ordered=False — o MongoDB pode otimizar melhor a escrita, e um documento
    duplicado (idEvento repetido) não interrompe o restante do lote.

    Mede o tempo de parede (wall clock) do processo de inserção do início ao
    fim: é essa métrica que alimenta a tabela do Teste 1 do enunciado.
    """
    total_inserido = 0
    inicio = time.perf_counter()

    for i in range(0, len(eventos), tamanho_lote):
        lote = eventos[i : i + tamanho_lote]
        try:
            resultado = colecao.insert_many(lote, ordered=False)
            total_inserido += len(resultado.inserted_ids)
        except BulkWriteError as exc:
            # Duplicatas de idEvento (índice único) não devem interromper a
            # carga do restante; contamos só o que de fato foi inserido.
            total_inserido += exc.details.get("nInserted", 0)

    tempo_total = time.perf_counter() - inicio
    return ResultadoCarga(
        total_lido=len(eventos),
        total_inserido=total_inserido,
        tempo_segundos=tempo_total,
        tamanho_lote=tamanho_lote,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga em massa de eventos sintéticos no MongoDB")
    parser.add_argument("--arquivo", required=True, help="Caminho para eventos.json ou eventos.jsonl")
    parser.add_argument("--lote", type=int, default=5000, help="Tamanho do lote de insert_many")
    parser.add_argument("--limite", type=int, default=None, help="Quantidade máxima de registros a carregar")
    parser.add_argument("--recriar", action="store_true", help="Apaga a coleção antes de carregar")
    args = parser.parse_args()

    colecao = get_collection()

    if args.recriar:
        colecao.drop()
        print("Coleção removida — recomeçando do zero.")

    garantir_indices(colecao)

    print(f"Lendo eventos de {args.arquivo} (limite={args.limite or 'nenhum'})...")
    inicio_leitura = time.perf_counter()
    eventos = ler_eventos(args.arquivo, limite=args.limite)
    tempo_leitura = time.perf_counter() - inicio_leitura
    print(f"{len(eventos):,} eventos lidos em {tempo_leitura:.2f}s.".replace(",", "."))

    resultado = inserir_em_lotes(colecao, eventos, tamanho_lote=args.lote)

    print("\nResultado da carga:")
    print(f"  Registros lidos:     {resultado.total_lido:,}".replace(",", "."))
    print(f"  Registros inseridos: {resultado.total_inserido:,}".replace(",", "."))
    print(f"  Tempo total:         {resultado.tempo_segundos:.2f} s")
    print(f"  Throughput:          {resultado.throughput_por_segundo:,.0f} docs/s".replace(",", "."))


if __name__ == "__main__":
    main()
