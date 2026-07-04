# dataset/

Esta pasta recebe os dados sintéticos gerados pelo notebook
`scripts/notebooks/gerador_dados_sinteticos_eventos_urbanos.ipynb`.

Arquivos esperados aqui após rodar o notebook:

- `eventos.json` — array JSON único (útil para `mongoimport --jsonArray` ou inspeção manual)
- `eventos.jsonl` — um objeto JSON por linha (formato recomendado — é o que os
  scripts `carga_massa.py` e `executar_testeN_*.py` esperam por padrão)
- `eventos.csv` — formato tabular, útil para inspeção rápida em planilhas

## Por que esta pasta está (quase) vazia no repositório

Datasets de 50.000/100.000 registros geram arquivos grandes (dezenas de MB) —
não é uma boa prática versionar isso no Git. Recomendação: adicione ao
`.gitignore` do repositório:

```
dataset/*.json
dataset/*.jsonl
dataset/*.csv
```

E documentem no relatório técnico (`documentacao/`) como o dataset foi gerado
e com qual seed, para que a geração seja reprodutível por quem for avaliar o
trabalho.
