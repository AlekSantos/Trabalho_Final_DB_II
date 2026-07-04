"""
Camada de acesso ao MongoDB — Sistema de Monitoramento de Eventos Urbanos
BD II - IC/UFRJ

Uso típico dentro do app Streamlit:

    from database import get_collection, garantir_indices

    colecao = get_collection()
    garantir_indices(colecao)   # idempotente, seguro rodar toda vez que o app inicia
"""
from __future__ import annotations

import os

import streamlit as st
from pymongo import ASCENDING, DESCENDING, GEOSPHERE, MongoClient
from pymongo.collection import Collection

def _resolver_mongo_uri() -> str:
    """Prioridade: variável de ambiente > st.secrets (Streamlit Cloud) > localhost.

    Usa try/except porque st.secrets lança exceção (em vez de retornar None)
    quando não existe nenhum secrets.toml configurado — o que é o caso normal
    em desenvolvimento local.
    """
    if uri := os.getenv("MONGO_URI"):
        return uri
    try:
        return st.secrets["MONGO_URI"]
    except (KeyError, FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return "mongodb://localhost:27017"


MONGO_URI = _resolver_mongo_uri()
DB_NAME = os.getenv("MONGO_DB", "eventos_urbanos")
COLLECTION_NAME = "eventos"


@st.cache_resource(show_spinner="Conectando ao MongoDB...")
def get_client() -> MongoClient:
    """Cria (uma única vez, graças ao cache do Streamlit) a conexão com o cluster.

    Funciona tanto com um único nó quanto com uma connection string de
    Replica Set, por exemplo:
    mongodb://no1:27017,no2:27017,no3:27017/?replicaSet=rsEventos
    """
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)


def get_collection() -> Collection:
    client = get_client()
    return client[DB_NAME][COLLECTION_NAME]


def garantir_indices(colecao: Collection) -> None:
    """Cria todos os índices necessários para as consultas obrigatórias do
    trabalho (seções 6.2 a 6.6). Operação idempotente: pode ser chamada toda
    vez que o app sobe, sem custo de recriar índices já existentes.
    """
    # 6.1 / unicidade do identificador de negócio
    colecao.create_index("idEvento", unique=True, name="idx_idEvento_unique")

    # 6.2 - Consulta por tipo
    colecao.create_index("tipo", name="idx_tipo")

    # 6.3 - Consulta por período
    colecao.create_index("dataHora", name="idx_dataHora")

    # 6.5 - Consulta por gravidade
    colecao.create_index("gravidade", name="idx_gravidade")

    # 6.6 - Estatísticas por bairro
    colecao.create_index("bairro", name="idx_bairro")

    # Índice composto para filtros combinados (ex.: tipo + intervalo de datas)
    colecao.create_index(
        [("tipo", ASCENDING), ("dataHora", DESCENDING)],
        name="idx_tipo_dataHora",
    )

    # 6.4 - Consulta geográfica nativa (ex.: $geoNear, $geoWithin)
    colecao.create_index([("location", GEOSPHERE)], name="idx_location_2dsphere")


def listar_indices(colecao: Collection) -> list[dict]:
    """Utilitário para exibir na aba de 'Administração' do Streamlit quais
    índices existem de fato no servidor — útil para o vídeo/demo do Teste 3."""
    return list(colecao.list_indexes())
