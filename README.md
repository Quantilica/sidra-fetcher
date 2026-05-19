# sidra-fetcher: Cliente Python para a API do IBGE/SIDRA

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square) ![Python](https://img.shields.io/badge/python-3.13+-blue.svg?style=flat-square)

Biblioteca Python para buscar e processar dados e metadados das APIs oficiais do [IBGE](https://www.ibge.gov.br/) — [Agregados v3](https://servicodados.ibge.gov.br/api/docs/agregados?versao=3) e [SIDRA](https://apisidra.ibge.gov.br). Fornece acesso tipado via dataclasses a pesquisas, agregados, períodos, territórios, variáveis e classificações, com clientes síncrono e assíncrono.

---

## Instalação

```bash
pip install git+https://github.com/Quantilica/sidra-fetcher.git
```

Com [uv](https://github.com/astral-sh/uv):

```bash
uv add "git+https://github.com/Quantilica/sidra-fetcher.git"
```

**Requisitos:** Python 3.13+

## Interface de Linha de Comando (CLI)

O `sidra-fetcher` inclui uma interface de linha de comando para exploração rápida de metadados.

### Uso Autônomo

```bash
# Listar todas as pesquisas
sidra-fetcher list pesquisas

# Listar agregados de uma pesquisa (ex: 73)
sidra-fetcher list agregados 73

# Ver metadados detalhados de um agregado (ex: 1612)
sidra-fetcher info 1612

# Listar períodos disponíveis
sidra-fetcher periods 1612
```

### Integração com `quantilica-cli`

Se o `quantilica-cli` estiver instalado no mesmo ambiente, o `sidra-fetcher` será detectado automaticamente como um plugin:

```bash
quantilica fetch sidra info 1612
```

---

## Uso Rápido

```python
from sidra_fetcher.fetcher import SidraClient

with SidraClient() as client:
    # Listar todas as pesquisas e seus agregados
    index = client.get_indice_pesquisas_agregados()
    print(index[0].nome, "->", index[0].agregados[0].nome)

    # Metadados completos do agregado 1705 (IPCA-15)
    agregado = client.get_agregado(1705)
    print(agregado.nome)
    print(f"Períodos: {len(agregado.periodos)}")
    print(f"Localidades: {len(agregado.localidades)}")
```

---

## API Python

### `SidraClient` (síncrono)

```python
from sidra_fetcher.fetcher import SidraClient

client = SidraClient(timeout=60)
```

Todos os métodos abaixo também funcionam via context manager: `with SidraClient() as client:`.

#### `get_indice_pesquisas_agregados()`

Retorna todas as pesquisas com o índice de agregados aninhado.

```python
index = client.get_indice_pesquisas_agregados()
# -> list[IndicePesquisaAgregados]

for pesquisa in index:
    print(pesquisa.id, pesquisa.nome)
    for agregado in pesquisa.agregados:
        print("  ", agregado.id, agregado.nome)
```

#### `get_agregado_metadados(agregado_id)`

Retorna os metadados completos de um agregado — variáveis, classificações, níveis territoriais e periodicidade.

```python
meta = client.get_agregado_metadados(1705)
# -> Agregado

print(meta.id, meta.nome)
print(meta.periodicidade.frequencia)   # ex: "mensal"
print([v.nome for v in meta.variaveis])
print([c.nome for c in meta.classificacoes])
```

#### `get_agregado_periodos(agregado_id)`

Retorna os períodos disponíveis de um agregado, com metadados temporais analisados.

```python
periodos = client.get_agregado_periodos(1705)
# -> list[Periodo]

for p in periodos:
    print(p.id, p.frequencia, p.data_inicio, p.data_fim)
    # ex: "202312  mensal  2023-12-01  2023-12-31"
```

Veja [Análise de Períodos](#análise-de-períodos) para a lista completa de campos do objeto `Periodo`.

#### `get_agregado_localidades(agregado_id, localidades_nivel)`

Retorna as localidades filtradas por um ou mais códigos de nível territorial (ex: `"N1"` para Brasil, `"N3"` para estados, `"N6"` para municípios).

```python
localidades = client.get_agregado_localidades(1705, "N3")
# -> list[Localidade]

for loc in localidades:
    print(loc.id, loc.nome, loc.nivel.id)
```

#### `get_agregado(agregado_id)`

Método de conveniência: busca metadados, períodos e todas as localidades declaradas em uma única chamada.

```python
agregado = client.get_agregado(1705)
# -> Agregado (com .periodos e .localidades preenchidos)
```

#### `get_acervo(acervo)`

Busca uma listagem de "acervo" (coleção). Use `AcervoEnum` para selecionar a coleção desejada.

```python
from sidra_fetcher.agregados import AcervoEnum

assuntos = client.get_acervo(AcervoEnum.ASSUNTO)
variaveis = client.get_acervo(AcervoEnum.VARIAVEL)
```

Valores disponíveis no `AcervoEnum`:

| Membro              | Descrição               |
|---------------------|-------------------------|
| `ASSUNTO`           | Tópicos / assuntos      |
| `CLASSIFICACAO`     | Classificações          |
| `NIVELTERRITORIAL`  | Níveis territoriais     |
| `PERIODO`           | Períodos                |
| `PERIODICIDADE`     | Periodicidades          |
| `VARIAVEL`          | Variáveis               |

---

### `AsyncSidraClient` (assíncrono)

Equivalente assíncrono do `SidraClient`. Todos os métodos são corrotinas. `get_agregado` busca metadados e períodos concorrentemente via `asyncio.gather`.

```python
import asyncio
from sidra_fetcher.fetcher import AsyncSidraClient

async def main():
    async with AsyncSidraClient() as client:
        index = await client.get_indice_pesquisas_agregados()
        agregado = await client.get_agregado(1705)
        print(len(agregado.periodos))

asyncio.run(main())
```

---

## Análise de Períodos

`get_agregado_periodos` analisa as strings de período retornadas pela API e as converte em objetos `Periodo` estruturados, com frequência detectada e intervalo de datas calculado automaticamente.

### Campos do objeto `Periodo`

| Campo         | Tipo              | Descrição                                                    |
|---------------|-------------------|--------------------------------------------------------------|
| `id`          | `str`             | ID bruto do período da API (ex: `"202312"`)                  |
| `literals`    | `list[str]`       | Representações legíveis (ex: `["dezembro de 2023"]`)         |
| `modificacao` | `dt.date`         | Data da última atualização dos dados do período              |
| `frequencia`  | `str \| None`     | Tipo de frequência detectado (ver tabela abaixo)             |
| `data_inicio` | `dt.date \| None` | Primeiro dia do período                                      |
| `data_fim`    | `dt.date \| None` | Último dia do período                                        |
| `ano`         | `int \| None`     | Ano                                                          |
| `mes`         | `int \| None`     | Mês (1–12); em trimestres móveis, o último mês               |
| `trimestre`   | `int \| None`     | Número do trimestre (1–4)                                    |
| `semestre`    | `int \| None`     | Número do semestre (1–2)                                     |
| `ano_fim`     | `int \| None`     | Ano final para períodos plurianuais                          |

### Tipos de frequência

| `frequencia`        | Exemplo de literal           | Intervalo de datas            |
|---------------------|------------------------------|-------------------------------|
| `mensal`            | `"janeiro de 2023"`          | 1 jan – 31 jan                |
| `trimestral`        | `"1º trimestre de 2023"`     | 1 jan – 31 mar                |
| `trimestre_movel`   | `"jan-fev-mar 2023"`         | 1 jan – 31 mar                |
| `semestral`         | `"1º semestre de 2023"`      | 1 jan – 30 jun                |
| `anual`             | `"2023"`                     | 1 jan – 31 dez                |
| `plurianual`        | `"2020/2023"`                | 1 jan 2020 – 31 dez 2023      |
| `nao_reconhecida`   | *(sem correspondência)*      | `None` / `None`               |

As constantes de frequência também são importáveis:

```python
from sidra_fetcher.periodos import (
    FREQUENCIA_MENSAL,
    FREQUENCIA_TRIMESTRAL,
    FREQUENCIA_TRIMESTRE_MOVEL,
    FREQUENCIA_SEMESTRAL,
    FREQUENCIA_ANUAL,
    FREQUENCIA_PLURIANUAL,
    FREQUENCIA_NAO_RECONHECIDA,
)
```

---

## Construtor de URL SIDRA

A classe `Parametro` constrói e analisa URLs de requisição SIDRA (`/values`).

```python
from sidra_fetcher.sidra import Parametro, Formato, Precisao

params = Parametro(
    agregado="1705",
    territorios={"3": ["all"]},   # todos os estados
    variaveis=["4099"],            # taxa de desemprego
    periodos=["202301", "202302"],
    classificacoes={"2": ["6794"]},
    formato=Formato.A,
    decimais={"": Precisao.M},
)

print(params.url())
# https://apisidra.ibge.gov.br/values/t/1705/n3/all/v/4099/p/202301,202302/c2/6794/h/y/f/a/d/m
```

### Parâmetros do `Parametro`

| Parâmetro       | Tipo                        | Segmento SIDRA    | Exemplo                               |
|-----------------|-----------------------------|-------------------|---------------------------------------|
| `agregado`      | `str`                       | `/t/{id}`         | `"1705"`                              |
| `territorios`   | `dict[str, list[str]]`      | `/n{nivel}/{ids}` | `{"3": ["all"]}` → `/n3/all`          |
| `variaveis`     | `list[str]`                 | `/v/{ids}`        | `["4099", "4100"]` ou `[]` → `/v/all` |
| `periodos`      | `list[str]`                 | `/p/{ids}`        | `["202301"]` ou `[]` → `/p/all`       |
| `classificacoes`| `dict[str, list[str]]`      | `/c{id}/{values}` | `{"2": ["6794"]}`                     |
| `cabecalho`     | `bool`                      | `/h/y` ou `/h/n`  | `True`                                |
| `formato`       | `Formato`                   | `/f/{code}`       | `Formato.A`                           |
| `decimais`      | `dict[str, Precisao]`       | `/d/{precisao}`   | `{"": Precisao.M}` → `/d/m`           |

### Analisar uma URL SIDRA existente

```python
from sidra_fetcher.sidra import parameter_from_url, parse_url

url = "https://apisidra.ibge.gov.br/values/t/1705/n3/all/v/4099/p/all/h/y/f/a/d/m"

params = parameter_from_url(url)
print(params.agregado)     # "1705"
print(params.territorios)  # {"3": ["all"]}

parsed = parse_url(url)
print(parsed["aggregate"])    # "1705"
print(parsed["territories"])  # {"3": ["all"]}
print(parsed["periods"])      # ["all"]
```

---

## Utilitários de Leitura e Achatamento

### Salvar e carregar metadados de agregados

```python
from sidra_fetcher.reader import save_agregado, load_agregado

# Salvar em JSON
save_agregado(agregado, "agregado_1705.json")

# Carregar do JSON (períodos são reanalisados automaticamente)
agregado = load_agregado("agregado_1705.json")
```

### Achatar metadados para análise

`flatten_aggregate_metadata` transforma a estrutura hierárquica variável × classificação em uma sequência de dicts — uma linha por combinação única de variável + categoria:

```python
from sidra_fetcher.reader import flatten_aggregate_metadata

raw_meta = client.get("https://servicodados.ibge.gov.br/api/v3/agregados/1705/metadados")

for row in flatten_aggregate_metadata(raw_meta):
    print(row["agregado"], row["D4N"], row.get("C5N"), row["MN"])
```

Cada linha contém:

| Chave          | Descrição                                   |
|----------------|---------------------------------------------|
| `agregado`     | Nome do agregado                            |
| `pesquisa`     | Nome da pesquisa                            |
| `assunto`      | Assunto / tópico                            |
| `frequencia`   | Frequência do agregado                      |
| `url_agregado` | URL do agregado                             |
| `D4C`/`D4N`    | ID / nome da variável                       |
| `D5C`/`D5N`    | ID / nome da primeira classificação         |
| `C5C`/`C5N`    | ID / nome da primeira categoria             |
| `MN`           | Unidade de medida                           |
| `nivel`        | Nível hierárquico da categoria              |

`flatten_surveys_metadata` achata o índice de pesquisas em uma lista de dicts `{pesquisa_id, pesquisa, agregado_id, agregado}`:

```python
from sidra_fetcher.reader import flatten_surveys_metadata

raw_index = client.get("https://servicodados.ibge.gov.br/api/v3/agregados")
rows = flatten_surveys_metadata(raw_index)
```

---

## Utilitários de Tamanho e Estatísticas

```python
from sidra_fetcher.stats import calculate_aggregate

stats = calculate_aggregate(agregado)
print(stats)
# {
#   "pesquisa_id": "...",
#   "agregado_id": 1705,
#   "n_localidades": 27,
#   "n_variaveis": 1,
#   "n_classificacoes": 1,
#   "n_dimensoes": 2,
#   "n_periodos": 84,
#   "period_size": 54,    # linhas por período
#   "total_size": 4536,   # total estimado de linhas
#   ...
# }
```

---

## Estrutura do Projeto

```
src/sidra_fetcher/
├── __init__.py          — logger do pacote
├── agregados.py         — dataclasses e construtores de URL para a API Agregados
├── fetcher.py           — SidraClient e AsyncSidraClient
├── periodos.py          — análise de strings de período e detecção de frequência
├── reader.py            — parsers JSON → dataclass e achatamento de metadados
├── sidra.py             — construtor de URL SIDRA (Parametro) e parsers
├── stats.py             — estatísticas de tamanho e dimensões
└── api_undocumented.py  — URLs de endpoints não documentados do IBGE
```

---

## Desenvolvimento

```bash
git clone https://github.com/Quantilica/sidra-fetcher.git
cd sidra-fetcher
uv sync --extra dev
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run python -m unittest discover -v tests
```

## Licença

MIT — veja [LICENSE](LICENSE).
