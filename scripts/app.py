"""
app.py — Painel Streamlit do Sistema de Monitoramento de Eventos Urbanos (RJ)
BD II - IC/UFRJ

Para rodar:
    streamlit run app.py

Pré-requisitos: MongoDB acessível (local, Docker ou Replica Set de 3 nós).
Configure a variável de ambiente MONGO_URI se não for localhost:27017
(veja database.py para detalhes, incluindo connection string de Replica Set).

Arquivos que este app espera encontrar na mesma pasta:
    models.py, database.py, queries.py
"""
from __future__ import annotations

from datetime import date, datetime, time

import pandas as pd
import streamlit as st
from pymongo.errors import PyMongoError

import queries
from database import garantir_indices, get_collection
from models import Evento, Localizacao, Reportante, StatusEvento, TipoEvento, TipoReportante

st.set_page_config(
    page_title="Monitoramento de Eventos Urbanos no Rio de Janeiro",
    page_icon='data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%23FFFFFF"><path d="M15 11V5l-3-3-3 3v2H3v14h18V11h-6zm-8 8H5v-2h2v2zm0-4H5v-2h2v2zm0-4H5V9h2v2zm6 8h-2v-2h2v2zm0-4h-2v-2h2v2zm0-4h-2V9h2v2zm0-4h-2V5h2v2zm6 12h-2v-2h2v2zm0-4h-2v-2h2v2z"/></svg>',
    layout="wide"
)

# Custom graphite sidebar styling
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        background-color: #36454F !important;
    }
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }
    /* Style the radio buttons check and text */
    [data-testid="stSidebar"] .st-bd {
        color: #FFFFFF !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Mesmos bairros e coordenadas usados no gerador de dados sintéticos, para que
# os eventos cadastrados manualmente fiquem geograficamente coerentes com o
# dataset carregado em massa.
BAIRROS_COM_CENTROIDE = {
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


@st.cache_resource(show_spinner="Conectando ao MongoDB e preparando índices...")
def inicializar_colecao():
    colecao = get_collection()
    garantir_indices(colecao)
    return colecao


def _proximo_id_evento(colecao) -> str:
    """Gera um idEvento sequencial simples (EVT + 8 dígitos).

    Observação: em cenários de inserção concorrente isso pode colidir; nesse
    caso o índice único em idEvento (ver database.garantir_indices) barra a
    duplicata e o formulário mostra o erro, bastando reenviar.
    """
    total = colecao.estimated_document_count()
    return f"EVT{total + 1:08d}"


def _mostrar_tabela(resultados: list[dict]) -> None:
    if not resultados:
        st.info("Nenhum resultado encontrado.")
        return
    df = pd.json_normalize(resultados)
    st.dataframe(df, width="stretch", hide_index=True)


try:
    colecao = inicializar_colecao()
    ERRO_CONEXAO: str | None = None
except PyMongoError as exc:
    colecao = None
    ERRO_CONEXAO = str(exc)


# ---------------------------------------------------------------------------
# Barra lateral / navegação
# ---------------------------------------------------------------------------
st.sidebar.title(":material/location_city: Monitoramento de Eventos Urbanos no Rio de Janeiro")
st.sidebar.caption("Trabalho Prático — BD II — IC/UFRJ")

if ERRO_CONEXAO:
    st.sidebar.error("Sem conexão com o MongoDB.")
else:
    total_docs = colecao.estimated_document_count()
    st.sidebar.metric("Eventos na base", f"{total_docs:,}".replace(",", "."))

opcoes_navegacao = {
    "inserir": ":material/add: Inserir Evento",
    "consultar": ":material/search: Consultar Eventos",
    "estatisticas": ":material/bar_chart: Estatísticas",
    "admin": ":material/settings: Administração",
}

pagina = st.sidebar.radio(
    "Navegação",
    options=list(opcoes_navegacao.keys()),
    format_func=lambda k: opcoes_navegacao[k],
)

if ERRO_CONEXAO:
    st.error(
        "**Não foi possível conectar ao MongoDB.**\n\n"
        f"Detalhe técnico: `{ERRO_CONEXAO}`\n\n"
        "Verifique se o(s) container(s) do MongoDB estão de pé e se a variável "
        "de ambiente `MONGO_URI` está configurada corretamente (veja `database.py`)."
    )
    st.stop()


# ---------------------------------------------------------------------------
# 6.1 — Inserção
# ---------------------------------------------------------------------------
if pagina == "inserir":
    st.header("Cadastrar novo evento urbano")

    # Geocoding Function
    def geocode_address(address: str) -> tuple[float, float, str] | None:
        import urllib.request
        import urllib.parse
        import json
        try:
            query = f"{address}, Rio de Janeiro, Brasil"
            url_encoded = urllib.parse.quote(query)
            url = (
                f"https://nominatim.openstreetmap.org/search"
                f"?q={url_encoded}&format=json&limit=1&addressdetails=1"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "BD2-UFRJ-Urban-Events-App"})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                if data:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    # Tenta encontrar o bairro nos campos do Nominatim
                    addr = data[0].get("address", {})
                    bairro_nominatim = (
                        addr.get("suburb")
                        or addr.get("neighbourhood")
                        or addr.get("city_district")
                        or addr.get("quarter")
                        or ""
                    ).strip()

                    # Tenta correspondência parcial com os bairros conhecidos
                    bairro_encontrado = None
                    bairro_lower = bairro_nominatim.lower()
                    for nome in BAIRROS_COM_CENTROIDE:
                        if nome.lower() in bairro_lower or bairro_lower in nome.lower():
                            bairro_encontrado = nome
                            break

                    # Fallback: bairro mais próximo pelas coordenadas
                    if not bairro_encontrado:
                        bairro_encontrado = min(
                            BAIRROS_COM_CENTROIDE,
                            key=lambda b: (
                                (BAIRROS_COM_CENTROIDE[b][0] - lat) ** 2
                                + (BAIRROS_COM_CENTROIDE[b][1] - lon) ** 2
                            ),
                        )

                    return lat, lon, bairro_encontrado
        except Exception as e:
            st.error(f"Erro ao buscar coordenadas: {e}")
        return None

    # Initialize session state for inputs if not present
    if "lat_inserir" not in st.session_state:
        st.session_state["lat_inserir"] = -22.9068
    if "lon_inserir" not in st.session_state:
        st.session_state["lon_inserir"] = -43.1729
    if "bairro_inserir" not in st.session_state:
        st.session_state["bairro_inserir"] = list(BAIRROS_COM_CENTROIDE.keys())[0]

    # Geocoding UI (outside the form to avoid form submission on click)
    st.text("Inserir endereço")
    col_addr, col_btn = st.columns([1, 1], vertical_alignment="bottom")
    with col_addr:
        endereco = st.text_input("Digite o endereço ou ponto de referência", placeholder="ex: Av. Atlântica, Copacabana", label_visibility="collapsed")
    with col_btn:
        buscar_coords = st.button("Buscar Coordenadas", use_container_width=True)

    if buscar_coords and endereco.strip():
        with st.spinner("Buscando coordenadas..."):
            resultado = geocode_address(endereco)
            if resultado:
                lat_geo, lon_geo, bairro_geo = resultado
                st.session_state["lat_inserir"] = lat_geo
                st.session_state["lon_inserir"] = lon_geo
                st.session_state["bairro_inserir"] = bairro_geo
                st.success(f"Endereço localizado em **{bairro_geo}** — {lat_geo:.6f}, {lon_geo:.6f}")
            else:
                st.error("Endereço não encontrado ou falha na busca.")

    # Bairro selector (outside form — on_change not allowed inside forms)
    def _on_change_bairro():
        lat_n, lon_n = BAIRROS_COM_CENTROIDE[st.session_state["bairro_inserir"]]
        st.session_state["lat_inserir"] = lat_n
        st.session_state["lon_inserir"] = lon_n

    bairro = st.selectbox(
        "Bairro",
        options=list(BAIRROS_COM_CENTROIDE.keys()),
        key="bairro_inserir",
        on_change=_on_change_bairro,
    )

    # Form
    with st.form("form_inserir_evento", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox("Tipo de evento", options=list(TipoEvento), format_func=lambda t: t.value)
            gravidade = st.slider("Gravidade", min_value=1, max_value=5, value=3)
            status = st.selectbox("Status", options=list(StatusEvento), format_func=lambda s: s.value)
        with col2:
            data_evento = st.date_input("Data do evento", value=date.today())
            hora_evento = st.time_input("Hora do evento", value=datetime.now().time().replace(microsecond=0))
            reportante_tipo = st.selectbox(
                "Tipo de reportante", options=list(TipoReportante), format_func=lambda r: r.value
            )
            reportante_id = st.text_input("Identificador do reportante", placeholder="ex.: USR0123")

        descricao = st.text_area("Descrição", placeholder="Descreva o evento...")

        enviado = st.form_submit_button("Cadastrar evento", type="primary")

    # Exibe coordenadas que serão usadas (fora do form, leitura do session_state)
    lat_usar = st.session_state.get("lat_inserir", -22.9068)
    lon_usar = st.session_state.get("lon_inserir", -43.1729)
    st.info(f":material/location_on: Coordenadas a serem cadastradas: **{lat_usar:.6f}**, **{lon_usar:.6f}**")

    if enviado:
        if not reportante_id.strip():
            st.warning("Informe o identificador do reportante.")
        elif not descricao.strip():
            st.warning("Informe uma descrição para o evento.")
        else:
            try:
                evento = Evento(
                    idEvento=_proximo_id_evento(colecao),
                    tipo=tipo,
                    descricao=descricao.strip(),
                    dataHora=datetime.combine(data_evento, hora_evento),
                    gravidade=gravidade,
                    status=status,
                    bairro=bairro,
                    localizacao=Localizacao(latitude=lat_usar, longitude=lon_usar),
                    reportante=Reportante(tipo=reportante_tipo, identificador=reportante_id.strip()),
                )
                id_criado = queries.inserir_evento(colecao, evento)
                st.success(f"Evento **{id_criado}** cadastrado com sucesso!")
            except ValueError as exc:
                st.error(f"Não foi possível cadastrar: {exc}")


# ---------------------------------------------------------------------------
# 6.2 / 6.3 / 6.4 / 6.5 — Consultas
# ---------------------------------------------------------------------------
elif pagina == "consultar":
    st.header("Consultar eventos")

    aba_tipo, aba_periodo, aba_geo, aba_gravidade = st.tabs(
        ["Por tipo", "Por período", "Geográfica (raio)", "Por gravidade"]
    )

    with aba_tipo:
        tipo_escolhido = st.selectbox(
            "Selecione o tipo de evento",
            options=list(TipoEvento),
            format_func=lambda t: t.value,
            key="tipo_busca",
        )
        if st.button("Buscar", key="btn_tipo"):
            resultados = queries.listar_por_tipo(colecao, tipo_escolhido)
            st.write(f"**{len(resultados)}** eventos encontrados.")
            _mostrar_tabela(resultados)

    with aba_periodo:
        col1, col2 = st.columns(2)
        with col1:
            data_inicio = st.date_input("Data inicial", key="periodo_inicio")
        with col2:
            data_fim = st.date_input("Data final", key="periodo_fim")
        if st.button("Buscar", key="btn_periodo"):
            if data_inicio > data_fim:
                st.warning("A data inicial deve ser anterior ou igual à data final.")
            else:
                inicio_dt = datetime.combine(data_inicio, time.min)
                fim_dt = datetime.combine(data_fim, time.max)
                resultados = queries.listar_por_periodo(colecao, inicio_dt, fim_dt)
                st.write(f"**{len(resultados)}** eventos encontrados.")
                _mostrar_tabela(resultados)

    with aba_geo:

        def _atualizar_coordenadas_do_bairro() -> None:
            # st.number_input com key só aplica o argumento "value" na primeira
            # renderização; nas seguintes ele mantém o valor do session_state
            # daquela key. Por isso, sem este callback, trocar o bairro recalcula
            # lat_ref/lon_ref mas os campos numéricos continuam com o valor antigo.
            lat, lon = BAIRROS_COM_CENTROIDE[st.session_state["geo_bairro"]]
            st.session_state["geo_lat"] = lat
            st.session_state["geo_lon"] = lon

        col1, col2, col3 = st.columns(3)
        with col1:
            bairro_ref = st.selectbox(
                "Centralizar busca no bairro",
                options=list(BAIRROS_COM_CENTROIDE.keys()),
                key="geo_bairro",
                on_change=_atualizar_coordenadas_do_bairro,
            )
        lat_ref, lon_ref = BAIRROS_COM_CENTROIDE[bairro_ref]
        with col2:
            latitude_busca = st.number_input("Latitude", value=lat_ref, format="%.6f", key="geo_lat")
        with col3:
            longitude_busca = st.number_input("Longitude", value=lon_ref, format="%.6f", key="geo_lon")
        raio_km = st.slider("Raio de busca (km)", min_value=1, max_value=30, value=5)

        if st.button("Buscar", key="btn_geo"):
            try:
                resultados = queries.buscar_por_raio(colecao, latitude_busca, longitude_busca, raio_km)
            except Exception:
                # Qualquer problema com a consulta geoespacial nativa (índice
                # ausente, driver, ou o backend não suportar $geoNear) cai
                # para o fallback em Python, em vez de quebrar a página
                # durante a demonstração ao vivo.
                st.info(
                    "Consulta geoespacial nativa indisponível — usando busca "
                    "alternativa (filtragem feita na aplicação)."
                )
                resultados = queries.buscar_por_raio_fallback(colecao, latitude_busca, longitude_busca, raio_km)
            st.write(f"**{len(resultados)}** eventos encontrados num raio de {raio_km} km.")
            _mostrar_tabela(resultados)
            if resultados:
                mapa_df = pd.DataFrame(
                    [
                        {"lat": r["localizacao"]["latitude"], "lon": r["localizacao"]["longitude"]}
                        for r in resultados
                    ]
                )
                st.map(mapa_df, size=30)

    with aba_gravidade:
        gravidade_min = st.slider("Gravidade mínima", min_value=1, max_value=5, value=3, key="grav_min")
        if st.button("Buscar", key="btn_gravidade"):
            resultados = queries.listar_por_gravidade_minima(colecao, gravidade_min)
            st.write(f"**{len(resultados)}** eventos encontrados com gravidade ≥ {gravidade_min}.")
            _mostrar_tabela(resultados)


# ---------------------------------------------------------------------------
# 6.6 — Estatísticas
# ---------------------------------------------------------------------------
elif pagina == "estatisticas":
    st.header("Estatísticas gerais")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Quantidade por tipo")
        dados_tipo = queries.contagem_por_tipo(colecao)
        if dados_tipo:
            df_tipo = pd.DataFrame(dados_tipo).set_index("tipo")
            st.bar_chart(df_tipo)
        else:
            st.info("Ainda não há dados suficientes.")

    with col2:
        st.subheader("Top 10 bairros")
        dados_bairro = queries.contagem_por_bairro(colecao, top_n=10)
        if dados_bairro:
            df_bairro = pd.DataFrame(dados_bairro).set_index("bairro")
            st.bar_chart(df_bairro)
        else:
            st.info("Ainda não há dados suficientes.")

    st.subheader("Evolução temporal")
    granularidade = st.radio("Agrupar por", options=["hora", "dia", "mes"], index=1, horizontal=True)
    dados_evolucao = queries.evolucao_temporal(colecao, granularidade)
    if dados_evolucao:
        df_evolucao = pd.DataFrame(dados_evolucao).set_index("periodo")
        st.line_chart(df_evolucao)
    else:
        st.info("Ainda não há dados suficientes.")

    st.subheader("Quantidade por status")
    dados_status = queries.contagem_por_status(colecao)
    if dados_status:
        df_status = pd.DataFrame(dados_status).set_index("status")
        st.bar_chart(df_status)


# ---------------------------------------------------------------------------
# Administração — útil para demonstrar a Parte Distribuída (Seção 7 / Teste 3)
# ---------------------------------------------------------------------------
elif pagina == "admin":
    st.header("Administração do cluster")

    st.subheader("Índices ativos na coleção `eventos`")
    try:
        indices = list(colecao.list_indexes())
        st.table(pd.DataFrame([{"nome": i["name"], "chave": dict(i["key"])} for i in indices]))
    except PyMongoError as exc:
        st.error(f"Não foi possível listar os índices: {exc}")

    st.subheader("Status do Replica Set")
    st.caption(
        "Use esta seção na demonstração do Teste 3 (falha de nó): derrube um dos "
        "containers do MongoDB e clique em **Atualizar status** para mostrar que o "
        "sistema continua respondendo com os nós restantes."
    )
    if st.button("Atualizar status"):
        try:
            status = colecao.database.client.admin.command("replSetGetStatus")
            membros = [
                {
                    "nó": m["name"],
                    "estado": m["stateStr"],
                    "saudável": "✅" if m["health"] == 1 else "❌",
                }
                for m in status["members"]
            ]
            st.table(pd.DataFrame(membros))
        except Exception as exc:
            # Captura ampla de propósito: em produção, um MongoDB rodando como
            # nó único (sem --replSet) responde com OperationFailure; qualquer
            # outro erro inesperado aqui não deve derrubar a página inteira
            # durante a demonstração ao vivo.
            st.info(
                "Não foi possível obter o status do Replica Set (o MongoDB pode "
                f"estar rodando como nó único, sem replicação). Detalhe: {exc}"
            )
