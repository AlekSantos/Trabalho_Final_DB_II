"""
Consultas e estatísticas — Sistema de Monitoramento de Eventos Urbanos
BD II - IC/UFRJ

Implementa, em cima da coleção `eventos` (ver models.py / database.py), todas
as funcionalidades obrigatórias do enunciado:

    6.1 Inserção
    6.2 Consulta por tipo
    6.3 Consulta por período
    6.4 Consulta geográfica (raio)
    6.5 Consulta por gravidade
    6.6 Estatísticas (por tipo, por bairro, evolução temporal)

Cada função recebe a `Collection` do pymongo como primeiro parâmetro, para
não acoplar este módulo a uma conexão global — facilita testes e reuso.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Literal

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from models import Evento, StatusEvento, TipoEvento

RAIO_TERRA_KM = 6371.0


# ---------------------------------------------------------------------------
# 6.1 Inserção
# ---------------------------------------------------------------------------
def inserir_evento(colecao: Collection, evento: Evento) -> str:
    """Insere um novo evento. Levanta ValueError se o idEvento já existir
    (idEvento tem índice único — ver database.garantir_indices)."""
    try:
        colecao.insert_one(evento.to_mongo_doc())
    except DuplicateKeyError as exc:
        raise ValueError(f"Já existe um evento com idEvento={evento.idEvento!r}") from exc
    return evento.idEvento


# ---------------------------------------------------------------------------
# 6.2 Consulta por tipo
# ---------------------------------------------------------------------------
def listar_por_tipo(colecao: Collection, tipo: TipoEvento | str, limite: int = 200) -> list[dict]:
    tipo_valor = tipo.value if isinstance(tipo, TipoEvento) else tipo
    cursor = (
        colecao.find({"tipo": tipo_valor}, {"_id": 0, "location": 0})
        .sort("dataHora", -1)
        .limit(limite)
    )
    return list(cursor)


# ---------------------------------------------------------------------------
# 6.3 Consulta por período
# ---------------------------------------------------------------------------
def listar_por_periodo(
    colecao: Collection, inicio: datetime, fim: datetime, limite: int = 500
) -> list[dict]:
    filtro = {"dataHora": {"$gte": inicio, "$lte": fim}}
    cursor = colecao.find(filtro, {"_id": 0, "location": 0}).sort("dataHora", 1).limit(limite)
    return list(cursor)


# ---------------------------------------------------------------------------
# 6.4 Consulta geográfica (raio)
# ---------------------------------------------------------------------------
def buscar_por_raio(
    colecao: Collection,
    latitude: float,
    longitude: float,
    raio_km: float,
    limite: int = 20000,
) -> list[dict]:
    """Busca eventos dentro de um raio (em km) a partir de um ponto, usando o
    índice geoespacial nativo do MongoDB ($geoNear). Requer o índice
    'idx_location_2dsphere' criado por database.garantir_indices().

    Retorna os documentos ordenados do mais próximo para o mais distante,
    com um campo extra 'distancia_km' calculado pelo próprio MongoDB.
    """
    pipeline = [
        {
            "$geoNear": {
                "near": {"type": "Point", "coordinates": [longitude, latitude]},
                "distanceField": "distancia_metros",
                "maxDistance": raio_km * 1000,
                "spherical": True,
            }
        },
        {"$addFields": {"distancia_km": {"$round": [{"$divide": ["$distancia_metros", 1000]}, 2]}}},
        {"$project": {"_id": 0, "location": 0, "distancia_metros": 0}},
        {"$limit": limite},
    ]
    return list(colecao.aggregate(pipeline))


def buscar_por_raio_fallback(
    colecao: Collection,
    latitude: float,
    longitude: float,
    raio_km: float,
    limite: int = 200,
) -> list[dict]:
    """Alternativa que filtra o raio na aplicação (Python), em vez de usar o
    índice geoespacial do banco. Útil caso o grupo troque de tecnologia para
    Cassandra ou Redis, que não têm suporte geoespacial nativo completo — o
    próprio enunciado permite essa abordagem nesse caso (Seção 6.4).

    Menos eficiente (varre mais documentos), mas funciona em qualquer banco.
    """
    resultados = []
    for doc in colecao.find({}, {"_id": 0}):
        lat2 = doc["localizacao"]["latitude"]
        lon2 = doc["localizacao"]["longitude"]
        distancia_km = _distancia_haversine_km(latitude, longitude, lat2, lon2)
        if distancia_km <= raio_km:
            doc.pop("location", None)
            doc["distancia_km"] = round(distancia_km, 2)
            resultados.append(doc)

    resultados.sort(key=lambda d: d["distancia_km"])
    return resultados[:limite]


def _distancia_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em linha reta entre duas coordenadas, em km (fórmula de Haversine)."""
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * RAIO_TERRA_KM * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# 6.5 Consulta por gravidade
# ---------------------------------------------------------------------------
def listar_por_gravidade_minima(
    colecao: Collection, gravidade_min: int, limite: int = 500
) -> list[dict]:
    filtro = {"gravidade": {"$gte": gravidade_min}}
    cursor = colecao.find(filtro, {"_id": 0, "location": 0}).sort("gravidade", -1).limit(limite)
    return list(cursor)


# ---------------------------------------------------------------------------
# 6.6 Estatísticas
# ---------------------------------------------------------------------------
def contagem_por_tipo(colecao: Collection) -> list[dict]:
    """Retorna [{'tipo': 'Alagamento', 'total': 35}, ...] ordenado do maior para o menor."""
    pipeline = [
        {"$group": {"_id": "$tipo", "total": {"$sum": 1}}},
        {"$project": {"_id": 0, "tipo": "$_id", "total": 1}},
        {"$sort": {"total": -1}},
    ]
    return list(colecao.aggregate(pipeline))


def contagem_por_bairro(colecao: Collection, top_n: int | None = None) -> list[dict]:
    """Retorna [{'bairro': 'Centro', 'total': 420}, ...] ordenado do maior para o menor.
    Passe top_n para limitar (ex.: top_n=10 para o Top 10 bairros)."""
    pipeline = [
        {"$group": {"_id": "$bairro", "total": {"$sum": 1}}},
        {"$project": {"_id": 0, "bairro": "$_id", "total": 1}},
        {"$sort": {"total": -1}},
    ]
    if top_n:
        pipeline.append({"$limit": top_n})
    return list(colecao.aggregate(pipeline))


Granularidade = Literal["hora", "dia", "mes"]

_FORMATO_POR_GRANULARIDADE = {
    "hora": "%Y-%m-%dT%H:00",
    "dia": "%Y-%m-%d",
    "mes": "%Y-%m",
}


def evolucao_temporal(colecao: Collection, granularidade: Granularidade = "dia") -> list[dict]:
    """Retorna [{'periodo': '2025-06-10', 'total': 12}, ...] ordenado cronologicamente.
    granularidade: 'hora', 'dia' (padrão) ou 'mes'."""
    formato = _FORMATO_POR_GRANULARIDADE[granularidade]
    pipeline = [
        {"$group": {"_id": {"$dateToString": {"format": formato, "date": "$dataHora"}}, "total": {"$sum": 1}}},
        {"$project": {"_id": 0, "periodo": "$_id", "total": 1}},
        {"$sort": {"periodo": 1}},
    ]
    return list(colecao.aggregate(pipeline))


def contagem_por_status(colecao: Collection) -> list[dict]:
    """Extra (não exigido, mas útil no dashboard): quantidade por status atual."""
    pipeline = [
        {"$group": {"_id": "$status", "total": {"$sum": 1}}},
        {"$project": {"_id": 0, "status": "$_id", "total": 1}},
        {"$sort": {"total": -1}},
    ]
    return list(colecao.aggregate(pipeline))
