import os
import json
import random
from datetime import datetime, timedelta
import pandas as pd

# Domínio da Simulação
TIPOS_EVENTOS = [
    "Acidente de Trânsito",
    "Alagamento",
    "Queda de Energia",
    "Incêndio",
    "Problema no Transporte Público",
    "Vazamento de Água",
    "Interdição de Via",
    "Deslizamento de Terra",
    "Tiroteio",
]

PESOS_TIPOS = [22, 16, 10, 9, 14, 8, 9, 4, 8]
STATUS_OPCOES = ["Aberto", "Em Andamento", "Resolvido", "Fechado"]
PESOS_STATUS = [35, 25, 25, 15]

BAIRROS = {
    "Centro": (-22.9068, -43.1729),
    "Tijuca": (-22.9249, -43.2277),
    "Copacabana": (-22.9711, -43.1822),
    "Ipanema": (-22.9838, -43.2096),
    "Leblon": (-22.9847, -43.2244),
    "Botafogo": (-22.9519, -43.1823),
    "Flamengo": (-22.9326, -43.1758),
    "Barra da Tijuca": (-23.0045, -43.3651),
    "Recreio dos Bandeirantes": (-23.0231, -43.4653),
    "Jacarepaguá": (-22.9569, -43.3639),
    "Campo Grande": (-22.9037, -43.5613),
    "Bangu": (-22.8792, -43.4659),
    "Madureira": (-22.8730, -43.3395),
    "Penha": (-22.8390, -43.2801),
    "Ilha do Governador": (-22.8098, -43.2075),
    "Santa Cruz": (-22.9192, -43.6864),
    "Realengo": (-22.8779, -43.4351),
    "Vila Isabel": (-22.9159, -43.2453),
    "Méier": (-22.9014, -43.2799),
    "Pavuna": (-22.8104, -43.3564),
    "Rocinha": (-22.9887, -43.2453),
    "Complexo do Alemão": (-22.8600, -43.2724),
    "Maré": (-22.8611, -43.2408),
    "São Cristóvão": (-22.8985, -43.2211),
    "Lagoa": (-22.9722, -43.2050),
    "Jardim Botânico": (-22.9707, -43.2222),
    "Gávea": (-22.9767, -43.2325),
    "Cidade de Deus": (-22.9469, -43.3628),
    "Anchieta": (-22.8267, -43.3897),
    "Guaratiba": (-23.0578, -43.5967),
}

REPORTANTE_TIPOS = ["Cidadao", "Sensor", "OrgaoPublico"]
PESOS_REPORTANTE = [60, 30, 10]
PREFIXO_IDENTIFICADOR = {"Cidadao": "USR", "Sensor": "SENSOR", "OrgaoPublico": "ORG"}

DATA_FIM = datetime(2026, 6, 30, 23, 59, 59)
DATA_INICIO = DATA_FIM - timedelta(days=365)
CIDADE = "Rio de Janeiro"

DESCRICOES = {
    "Acidente de Trânsito": [
        "Colisão entre dois veículos na via principal",
        "Atropelamento registrado por transeunte",
        "Engavetamento envolvendo múltiplos veículos",
        "Colisão com poste, trânsito lento no local",
    ],
    "Alagamento": [
        "Rua completamente interditada devido ao volume de chuva",
        "Acúmulo de água impede passagem de veículos",
        "Bueiro entupido causa alagamento na via",
        "Nível da água subindo próximo a residências",
    ],
    "Queda de Energia": [
        "Falta de energia elétrica reportada por moradores",
        "Transformador danificado após tempestade",
        "Interrupção no fornecimento afeta quarteirão inteiro",
    ],
    "Incêndio": [
        "Princípio de incêndio em imóvel residencial",
        "Incêndio em vegetação próximo à via",
        "Fogo em veículo estacionado, bombeiros acionados",
    ],
    "Problema no Transporte Público": [
        "Ônibus quebrado obstruindo faixa de rolamento",
        "Atraso significativo reportado por usuários",
        "Falha mecânica em composição do sistema sobre trilhos",
    ],
    "Vazamento de Água": [
        "Rompimento de tubulação causa vazamento na via",
        "Vazamento constante reportado há mais de um dia",
        "Desperdício de água por adutora danificada",
    ],
    "Interdição de Via": [
        "Via interditada para obras de manutenção",
        "Bloqueio temporário devido a evento público",
        "Interdição por risco de desabamento parcial",
    ],
    "Deslizamento de Terra": [
        "Deslizamento de encosta após fortes chuvas",
        "Risco iminente de deslizamento reportado por moradores",
        "Barreira cede parcialmente sobre a via",
    ],
    "Tiroteio": [
        "Disparos reportados por moradores da região",
        "Confronto reportado nas proximidades",
        "Ocorrência policial em andamento no local",
    ],
}

def _jitter_coordenada(lat, lon, raio_graus=0.028):
    return (
        round(lat + random.uniform(-raio_graus, raio_graus), 6),
        round(lon + random.uniform(-raio_graus, raio_graus), 6),
    )

def _data_hora_aleatoria():
    delta = DATA_FIM - DATA_INICIO
    segundos_aleatorios = random.randint(0, int(delta.total_seconds()))
    return DATA_INICIO + timedelta(seconds=segundos_aleatorios)

def gerar_evento(indice: int, largura_id: int = 8) -> dict:
    tipo = random.choices(TIPOS_EVENTOS, weights=PESOS_TIPOS, k=1)[0]
    bairro = random.choice(list(BAIRROS.keys()))
    lat_base, lon_base = BAIRROS[bairro]
    lat, lon = _jitter_coordenada(lat_base, lon_base)

    reportante_tipo = random.choices(REPORTANTE_TIPOS, weights=PESOS_REPORTANTE, k=1)[0]
    reportante_num = random.randint(1, 5000)
    identificador = f"{PREFIXO_IDENTIFICADOR[reportante_tipo]}{reportante_num:04d}"

    return {
        "idEvento": f"EVT{indice:0{largura_id}d}",
        "tipo": tipo,
        "descricao": random.choice(DESCRICOES[tipo]),
        "dataHora": _data_hora_aleatoria().strftime("%Y-%m-%dT%H:%M:%S"),
        "gravidade": random.randint(1, 5),
        "status": random.choices(STATUS_OPCOES, weights=PESOS_STATUS, k=1)[0],
        "bairro": bairro,
        "cidade": CIDADE,
        "localizacao.latitude": lat,
        "localizacao.longitude": lon,
        "reportante.tipo": reportante_tipo,
        "reportante.identificador": identificador,
    }

def main():
    SEED = 42
    random.seed(SEED)
    
    # 100.000 registros (volume máximo para os experimentos)
    quantidade = 100000 
    print(f"Gerando {quantidade:,} eventos sintéticos...".replace(",", "."))
    
    largura_id = max(8, len(str(quantidade)))
    eventos_achatados = [
        gerar_evento(i, largura_id=largura_id)
        for i in range(1, quantidade + 1)
    ]
    
    df_eventos = pd.DataFrame(eventos_achatados)
    
    PASTA_SAIDA = "./dataset"
    os.makedirs(PASTA_SAIDA, exist_ok=True)
    
    def _linha_para_evento(row):
        return {
            "idEvento": row["idEvento"],
            "tipo": row["tipo"],
            "descricao": row["descricao"],
            "dataHora": row["dataHora"],
            "gravidade": int(row["gravidade"]),
            "status": row["status"],
            "bairro": row["bairro"],
            "cidade": CIDADE,
            "localizacao": {
                "latitude": row["localizacao.latitude"],
                "longitude": row["localizacao.longitude"],
            },
            "reportante": {
                "tipo": row["reportante.tipo"],
                "identificador": row["reportante.identificador"],
            },
        }

    eventos_finais = [_linha_para_evento(r) for _, r in df_eventos.iterrows()]
    
    # 1) JSON (array único)
    caminho_json = os.path.join(PASTA_SAIDA, "eventos.json")
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(eventos_finais, f, ensure_ascii=False, indent=2)
        
    # 2) JSON Lines
    caminho_jsonl = os.path.join(PASTA_SAIDA, "eventos.jsonl")
    with open(caminho_jsonl, "w", encoding="utf-8") as f:
        for evento in eventos_finais:
            f.write(json.dumps(evento, ensure_ascii=False))
            f.write("\n")
            
    # 3) CSV
    caminho_csv = os.path.join(PASTA_SAIDA, "eventos.csv")
    df_eventos.to_csv(caminho_csv, index=False, encoding="utf-8")
    
    print("Arquivos exportados na pasta ./dataset com sucesso!")

if __name__ == "__main__":
    main()
