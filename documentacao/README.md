# documentacao/

Esta pasta deve conter o **Relatório Técnico** (máximo 6 a 8 páginas) exigido
no enunciado, com a seguinte estrutura obrigatória:

1. Nome do trabalho e componentes
2. Introdução
3. Fundamentação Teórica
4. Modelagem dos Dados
5. Arquitetura Implementada
6. Configuração
7. Resultados Experimentais
8. Discussão
9. Conclusão

## Material de apoio já disponível para escrever cada seção

| Seção do relatório | Onde buscar o conteúdo |
|---|---|
| 4. Modelagem dos Dados | `scripts/models.py` (estrutura do documento, índices) |
| 5. Arquitetura Implementada | `docker/docker-compose.yml` (replica set de 3 nós + app) |
| 7. Resultados Experimentais | CSVs e gráficos gerados por `executar_teste1/2/3_*.py` (salvos aqui mesmo, em `documentacao/`, se você não alterou o parâmetro `--saida` dos scripts) |

Depois de rodar os três testes, os arquivos abaixo devem aparecer nesta pasta
automaticamente (é o caminho padrão configurado nos scripts):

```
resultados_teste1_insercao.csv / .png
resultados_teste2_consultas.csv / .png
resultados_teste3_falha_no.csv
```

Cole essas tabelas e gráficos diretamente na Seção 7 do relatório.
