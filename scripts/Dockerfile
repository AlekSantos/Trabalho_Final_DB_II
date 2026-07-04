# Dockerfile do app Streamlit — Sistema de Monitoramento de Eventos Urbanos
# BD II - IC/UFRJ
#
# Espera encontrar, na mesma pasta: app.py, models.py, database.py, queries.py,
# requirements.txt (todos os arquivos gerados nas etapas anteriores do trabalho).

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
