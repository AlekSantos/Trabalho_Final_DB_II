# Sistema Distribuído de Monitoramento e Análise de Eventos Urbanos

Trabalho Prático — Bancos de Dados II — IC/UFRJ
Prof. Maria Luiza e Sergio Serra

Tecnologia escolhida: **MongoDB** (Opção A — Banco de Documentos), com Replica
Set de 3 nós emulado via Docker.

## Estrutura do repositório

```
.
├── scripts/            Código-fonte da aplicação e dos experimentos
│   ├── notebooks/       Notebook gerador dos dados sintéticos
│   ├── app.py            App Streamlit (inserção, consultas, estatísticas, admin)
│   ├── models.py         Modelagem dos dados (Pydantic)
│   ├── database.py       Conexão com o MongoDB e criação de índices
│   ├── queries.py        Consultas e agregações (Seções 6.1 a 6.6)
│   ├── carga_massa.py    Motor de carga em lote (insert_many)
│   ├── executar_teste1_insercao.py   Teste 1 — tempo de inserção
│   ├── executar_teste2_consultas.py  Teste 2 — tempo de resposta das consultas
│   ├── executar_teste3_falha_no.py   Teste 3 — tolerância a falhas
│   ├── requirements.txt
│   └── Dockerfile
├── dataset/            Dados sintéticos gerados (ver dataset/README.md)
├── docker/             Ambiente distribuído (3 nós MongoDB + app)
│   ├── docker-compose.yml
│   └── mongo-init.js
└── documentacao/       Relatório técnico (ver documentacao/README.md)
```

## Passo a passo para rodar tudo do zero

### 1. Gerar o dataset sintético

Abra `scripts/notebooks/gerador_dados_sinteticos_eventos_urbanos.ipynb`, escolha
o volume desejado (Pequeno/Médio/Grande/Personalizado) e exporte. Copie os
arquivos gerados (`eventos.json`, `eventos.jsonl`, `eventos.csv`) para a pasta
`dataset/` na raiz do repositório.

### 2. Subir o cluster MongoDB + o app

```bash
cd docker
docker compose up -d --build
```

Aguarde ~15s para os healthchecks passarem e o serviço `mongo-init` iniciar o
replica set automaticamente (ele aparece como "Exited (0)" ao terminar — isso
é esperado, não é erro). Confirme com:

```bash
docker compose logs mongo-init
```

O app fica disponível em **http://localhost:8501**.

### 3. Rodar os experimentos (Seção 8 do enunciado)

Sempre via `docker compose run`, para evitar problemas de resolução de nome
do replica set fora da rede Docker (ver aviso abaixo):

```bash
# Teste 1 — tempo de inserção
docker compose run --rm --entrypoint python app executar_teste1_insercao.py \
    --arquivo dataset/eventos.jsonl

# Teste 2 — tempo de resposta das consultas
docker compose run --rm --entrypoint python app executar_teste2_consultas.py \
    --arquivo dataset/eventos.jsonl

# Teste 3 — falha de nó (modo manual: pausa e pede pra você derrubar o container)
docker compose run --rm --entrypoint python app executar_teste3_falha_no.py
```

Durante o Teste 3, derrube um nó em **outro terminal do host** normalmente:
```bash
docker stop mongo2
# ... o script detecta e mostra que o sistema continua respondendo ...
docker start mongo2
```

### 4. Verificar o status do Replica Set manualmente (opcional)

```bash
docker exec -it mongo1 mongosh
rs.status()
```

## Aviso importante: hostname do replica set

Se você tentar rodar os scripts Python **diretamente na sua máquina** (fora do
Docker) contra este cluster, a primeira conexão em `localhost:27017` funciona,
mas o driver do MongoDB descobre os outros membros do replica set pelos nomes
internos (`mongo2`, `mongo3`), que não existem fora da rede Docker — a conexão
trava ou falha silenciosamente. Por isso todos os comandos acima usam
`docker compose run`, que roda o script dentro da mesma rede Docker do
cluster.

## Critérios de avaliação cobertos por cada parte

| Item do enunciado | Onde está |
|---|---|
| Modelagem NoSQL | `scripts/models.py`, `documentacao/` |
| Consultas e estatísticas | `scripts/queries.py`, `scripts/app.py` |
| Ambiente distribuído | `docker/` |
| Experimentos e análise | `scripts/executar_teste1/2/3_*.py`, resultados em `documentacao/` |
| Relatório e apresentação | `documentacao/` |
