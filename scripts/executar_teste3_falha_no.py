"""
executar_teste3_falha_no.py — Automatiza o Teste 3 (Seção 8) e serve de roteiro
para a demonstração da Parte Distribuída (Seção 7) do enunciado.

Procedimento cobrado no enunciado:
    1. Inserir dados.        (já deve estar feito — rode antes o Teste 1)
    2. Desligar um nó.
    3. Executar consultas.
    4. Verificar se o sistema continua funcionando.

Este script cobre os passos 2 a 4, com duas formas de derrubar o nó:

  --modo manual (padrão): o script pausa e pede para VOCÊ derrubar (e depois
      subir de volta) o container do MongoDB pelo terminal. Mais previsível
      para gravar a demonstração/vídeo, porque você controla o timing.

  --modo auto: o script executa "docker stop/start <container>" sozinho.
      Use --container para indicar o nome do container a derrubar.

Uso:
    python executar_teste3_falha_no.py
    python executar_teste3_falha_no.py --modo auto --container mongo-no2
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import time
from pathlib import Path
from typing import Callable

from pymongo.errors import PyMongoError

import queries
from database import get_collection
from models import TipoEvento

TIPO_TESTE = TipoEvento.ALAGAMENTO
TENTATIVAS_APOS_FALHA_PADRAO = 10
INTERVALO_ENTRE_TENTATIVAS_S_PADRAO = 2.0
ESPERA_REINTEGRACAO_S_PADRAO = 5.0


def _executar_consulta_com_retentativas(
    funcao_consulta: Callable[[], list], tentativas: int, intervalo_s: float
) -> dict:
    """Tenta executar `funcao_consulta` várias vezes, com pequenas pausas
    entre tentativas. Isso é necessário porque, durante a eleição de um novo
    nó primário no Replica Set (que leva alguns segundos), o driver pode
    momentaneamente não conseguir rotear a operação — não é uma falha real
    do sistema, é a janela normal de recuperação que o próprio enunciado
    pede para observar.
    """
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        inicio = time.perf_counter()
        try:
            resultados = funcao_consulta()
            tempo_ms = (time.perf_counter() - inicio) * 1000
            return {
                "sucesso": True,
                "tentativas_necessarias": tentativa,
                "tempo_resposta_ms": round(tempo_ms, 2),
                "total_resultados": len(resultados),
                "erro": None,
            }
        except PyMongoError as exc:
            ultimo_erro = exc
            print(
                f"    tentativa {tentativa}/{tentativas} falhou "
                f"({exc.__class__.__name__}), tentando de novo em {intervalo_s}s..."
            )
            time.sleep(intervalo_s)

    return {
        "sucesso": False,
        "tentativas_necessarias": tentativas,
        "tempo_resposta_ms": None,
        "total_resultados": 0,
        "erro": str(ultimo_erro),
    }


def _controlar_container(acao: str, container: str) -> None:
    comando = ["docker", acao, container]
    print(f"  Executando: {' '.join(comando)}")
    resultado = subprocess.run(comando, capture_output=True, text=True)
    if resultado.returncode != 0:
        print(f"  Aviso: comando retornou código {resultado.returncode}. stderr: {resultado.stderr.strip()}")
    else:
        print("  OK.")


def executar(
    modo: str,
    container: str | None,
    saida_csv: str,
    colecao=None,
    tentativas_apos_falha: int = TENTATIVAS_APOS_FALHA_PADRAO,
    intervalo_entre_tentativas_s: float = INTERVALO_ENTRE_TENTATIVAS_S_PADRAO,
    espera_reintegracao_s: float = ESPERA_REINTEGRACAO_S_PADRAO,
) -> list[dict]:
    colecao = colecao if colecao is not None else get_collection()

    def consulta_de_teste():
        return queries.listar_por_tipo(colecao, TIPO_TESTE, limite=10_000)

    linhas_csv = []

    print("Etapa 1/4 — Consulta baseline (todos os nós ativos)")
    baseline = _executar_consulta_com_retentativas(consulta_de_teste, tentativas=1, intervalo_s=0)
    print(f"  {baseline['total_resultados']} resultados em {baseline['tempo_resposta_ms']} ms")
    baseline["etapa"] = "1_baseline_todos_os_nos"
    linhas_csv.append(baseline)

    print("\nEtapa 2/4 — Derrubando um nó")
    if modo == "auto":
        if not container:
            raise SystemExit("--modo auto exige --container <nome_do_container>")
        _controlar_container("stop", container)
    else:
        input(
            "  Derrube manualmente um dos nós do MongoDB agora "
            "(ex.: docker stop <nome_do_container>) e pressione ENTER para continuar..."
        )

    print("\nEtapa 3/4 — Executando a mesma consulta com o nó fora do ar")
    apos_falha = _executar_consulta_com_retentativas(
        consulta_de_teste, tentativas=tentativas_apos_falha, intervalo_s=intervalo_entre_tentativas_s
    )
    if apos_falha["sucesso"]:
        print(
            f"  OK — sistema continuou respondendo! {apos_falha['total_resultados']} "
            f"resultados em {apos_falha['tempo_resposta_ms']} ms "
            f"(precisou de {apos_falha['tentativas_necessarias']} tentativa(s))."
        )
    else:
        print(
            f"  FALHOU — sistema não respondeu após {tentativas_apos_falha} tentativas. "
            f"Erro: {apos_falha['erro']}"
        )
    apos_falha["etapa"] = "2_com_no_derrubado"
    linhas_csv.append(apos_falha)

    print("\nEtapa 4/4 — Restaurando o nó")
    if modo == "auto":
        _controlar_container("start", container)
    else:
        input("  Suba o nó novamente (ex.: docker start <nome_do_container>) e pressione ENTER para finalizar...")

    print(f"  Aguardando {espera_reintegracao_s:.0f}s para o nó reintegrar ao Replica Set...")
    time.sleep(espera_reintegracao_s)
    apos_recuperacao = _executar_consulta_com_retentativas(
        consulta_de_teste, tentativas=tentativas_apos_falha, intervalo_s=intervalo_entre_tentativas_s
    )
    apos_recuperacao["etapa"] = "3_no_restaurado"
    linhas_csv.append(apos_recuperacao)

    _salvar_csv(linhas_csv, saida_csv)
    _imprimir_resumo(baseline, apos_falha, apos_recuperacao)
    return linhas_csv


def _salvar_csv(linhas: list[dict], caminho: str) -> None:
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    campos = ["etapa", "sucesso", "tentativas_necessarias", "tempo_resposta_ms", "total_resultados", "erro"]
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({k: linha.get(k) for k in campos})
    print(f"\nResultados salvos em {caminho}")


def _imprimir_resumo(baseline: dict, apos_falha: dict, apos_recuperacao: dict) -> None:
    print("\n=== Resumo do Teste 3 (para colar no relatório) ===")
    print(f"{'Etapa':<28} | {'Sucesso':<8} | {'Resultados':>10} | {'Tempo (ms)':>10}")
    for nome, dados in [
        ("Baseline (todos os nós)", baseline),
        ("Com 1 nó derrubado", apos_falha),
        ("Após restaurar o nó", apos_recuperacao),
    ]:
        print(
            f"{nome:<28} | {str(dados['sucesso']):<8} | "
            f"{dados['total_resultados']:>10} | {str(dados['tempo_resposta_ms']):>10}"
        )

    dados_consistentes = (
        baseline["total_resultados"] == apos_falha["total_resultados"] == apos_recuperacao["total_resultados"]
    )
    if apos_falha["sucesso"] and dados_consistentes:
        print(
            "\n✅ Tolerância a falhas CONFIRMADA: o sistema continuou respondendo "
            "com a mesma quantidade de dados mesmo com um nó fora do ar."
        )
    elif apos_falha["sucesso"]:
        print(
            "\n⚠️  O sistema continuou respondendo, mas a quantidade de resultados "
            "mudou entre as etapas — investigue se há inconsistência de replicação."
        )
    else:
        print(
            "\n❌ O sistema NÃO conseguiu responder com o nó derrubado. Verifique se "
            "o cluster está configurado como Replica Set (não como nós isolados) e "
            "se o MONGO_URI lista todos os hosts."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa o Teste 3 (falha de nó) do trabalho de BD II")
    parser.add_argument("--modo", choices=["manual", "auto"], default="manual")
    parser.add_argument("--container", default=None, help="Nome do container Docker a derrubar (modo auto)")
    parser.add_argument("--tentativas", type=int, default=TENTATIVAS_APOS_FALHA_PADRAO)
    parser.add_argument("--intervalo", type=float, default=INTERVALO_ENTRE_TENTATIVAS_S_PADRAO)
    parser.add_argument("--espera-reintegracao", type=float, default=ESPERA_REINTEGRACAO_S_PADRAO)
    parser.add_argument("--saida", default="documentacao/resultados_teste3_falha_no.csv")
    args = parser.parse_args()

    executar(
        args.modo,
        args.container,
        args.saida,
        tentativas_apos_falha=args.tentativas,
        intervalo_entre_tentativas_s=args.intervalo,
        espera_reintegracao_s=args.espera_reintegracao,
    )


if __name__ == "__main__":
    main()
