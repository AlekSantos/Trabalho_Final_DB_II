"""
Modelagem dos dados — Sistema Distribuído de Monitoramento de Eventos Urbanos
BD II - IC/UFRJ

Define os modelos Pydantic usados tanto para validar entradas no Streamlit
(formulário de inserção) quanto para serializar documentos antes de gravá-los
no MongoDB.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TipoEvento(str, Enum):
    ACIDENTE_TRANSITO = "Acidente de Trânsito"
    ALAGAMENTO = "Alagamento"
    QUEDA_ENERGIA = "Queda de Energia"
    INCENDIO = "Incêndio"
    TRANSPORTE_PUBLICO = "Problema no Transporte Público"
    VAZAMENTO_AGUA = "Vazamento de Água"
    INTERDICAO_VIA = "Interdição de Via"
    DESLIZAMENTO_TERRA = "Deslizamento de Terra"
    TIROTEIO = "Tiroteio"


class StatusEvento(str, Enum):
    ABERTO = "Aberto"
    EM_ANDAMENTO = "Em Andamento"
    RESOLVIDO = "Resolvido"
    FECHADO = "Fechado"


class TipoReportante(str, Enum):
    CIDADAO = "Cidadao"
    SENSOR = "Sensor"
    ORGAO_PUBLICO = "OrgaoPublico"


class Localizacao(BaseModel):
    """Estrutura exigida literalmente pelo enunciado do trabalho."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    def to_geojson(self) -> dict:
        """Converte para o formato GeoJSON exigido pelo índice 2dsphere do MongoDB.

        Atenção: GeoJSON usa a ordem [longitude, latitude], invertida em
        relação à ordem natural que usamos no restante do sistema.
        """
        return {"type": "Point", "coordinates": [self.longitude, self.latitude]}


class Reportante(BaseModel):
    tipo: TipoReportante
    identificador: str = Field(..., min_length=1, max_length=30)


class Evento(BaseModel):
    idEvento: str = Field(..., pattern=r"^EVT\d{6,}$")
    tipo: TipoEvento
    descricao: str = Field(..., min_length=1, max_length=500)
    dataHora: datetime
    gravidade: int = Field(..., ge=1, le=5)
    status: StatusEvento = StatusEvento.ABERTO
    bairro: str = Field(..., min_length=1, max_length=60)
    cidade: str = "Rio de Janeiro"
    localizacao: Localizacao
    reportante: Reportante

    def to_mongo_doc(self) -> dict:
        """Serializa o evento para o formato final gravado no MongoDB,
        incluindo o campo geoespacial derivado 'location'.

        Importante: usamos model_dump() em modo Python (não modo "json"),
        para que 'dataHora' permaneça como datetime nativo. Se fosse
        convertido para string, comparações de intervalo ($gte/$lte) e
        agregações como $dateToString parariam de funcionar corretamente.
        """
        doc = self.model_dump(mode="python")
        doc["tipo"] = self.tipo.value
        doc["status"] = self.status.value
        doc["reportante"]["tipo"] = self.reportante.tipo.value
        doc["localizacao"] = {
            "latitude": self.localizacao.latitude,
            "longitude": self.localizacao.longitude,
        }
        doc["location"] = self.localizacao.to_geojson()
        return doc

    @classmethod
    def from_mongo_doc(cls, doc: dict) -> "Evento":
        """Reconstrói um Evento a partir de um documento lido do MongoDB,
        ignorando o campo interno 'location' e o '_id' do Mongo.
        """
        dados = {k: v for k, v in doc.items() if k not in ("_id", "location")}
        return cls(**dados)
