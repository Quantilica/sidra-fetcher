# sidra-fetcher

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**sidra-fetcher** is a Python library for fetching and processing data and metadata from [IBGE](https://www.ibge.gov.br/)'s official APIs — [Agregados v3](https://servicodados.ibge.gov.br/api/docs/agregados?versao=3) and [SIDRA](https://apisidra.ibge.gov.br). It provides typed, dataclass-based access to surveys, aggregates, periods, territorial levels, variables, and classifications.

---

## Features

- Synchronous (`SidraClient`) and asynchronous (`AsyncSidraClient`) HTTP clients with automatic retry logic
- Typed Python dataclasses for all API responses (aggregates, periods, localities, variables, classifications)
- Temporal parsing for all Brazilian period formats: monthly, quarterly, rolling quarter, semiannual, annual, and multi-annual
- SIDRA `/values` URL builder and parser (`Parametro`) with support for all request segments
- Utilities to flatten aggregate metadata into tabular structures for data analysis
- Save and load aggregate metadata to/from JSON
- Size and dimension statistics for planning bulk downloads

---

## Installation

```bash
pip install sidra-fetcher
```

With [uv](https://github.com/astral-sh/uv):

```bash
uv add sidra-fetcher
```

**Requirements:** Python 3.13+

---

## Quick Start

```python
from sidra_fetcher.fetcher import SidraClient

with SidraClient() as client:
    # List all surveys and their aggregates
    index = client.get_indice_pesquisas_agregados()
    print(index[0].nome, "->", index[0].agregados[0].nome)

    # Full metadata for aggregate 1705 (IPCA-15 - de fev/2012 até jan/2020)
    agregado = client.get_agregado(1705)
    print(agregado.nome)
    print(f"Periods: {len(agregado.periodos)}")
    print(f"Localities: {len(agregado.localidades)}")
```

---

## Agregados API

### `SidraClient` (synchronous)

```python
from sidra_fetcher.fetcher import SidraClient

client = SidraClient(timeout=60)
```

All methods below can also be used as a context manager via `with SidraClient() as client:`.

#### `get_indice_pesquisas_agregados()`

Returns all surveys with their nested aggregate index.

```python
index = client.get_indice_pesquisas_agregados()
# -> list[IndicePesquisaAgregados]

for pesquisa in index:
    print(pesquisa.id, pesquisa.nome)
    for agregado in pesquisa.agregados:
        print("  ", agregado.id, agregado.nome)
```

#### `get_agregado_metadados(agregado_id)`

Returns full metadata for a single aggregate — variables, classifications, territorial levels and periodicidade.

```python
meta = client.get_agregado_metadados(1705)
# -> Agregado

print(meta.id, meta.nome)
print(meta.periodicidade.frequencia)   # e.g. "mensal"
print([v.nome for v in meta.variaveis])
print([c.nome for c in meta.classificacoes])
```

#### `get_agregado_periodos(agregado_id)`

Returns available periods for an aggregate, with parsed temporal metadata.

```python
periodos = client.get_agregado_periodos(1705)
# -> list[Periodo]

for p in periodos:
    print(p.id, p.frequencia, p.data_inicio, p.data_fim)
    # e.g. "202312  mensal  2023-12-01  2023-12-31"
```

See [Period Parsing](#period-parsing) for the full list of fields on `Periodo`.

#### `get_agregado_localidades(agregado_id, localidades_nivel)`

Returns localities filtered by one or more territorial level codes (e.g. `"N1"` for Brazil, `"N3"` for states, `"N6"` for municipalities).

```python
localidades = client.get_agregado_localidades(1705, "N3")
# -> list[Localidade]

for loc in localidades:
    print(loc.id, loc.nome, loc.nivel.id)
```

#### `get_agregado(agregado_id)`

Convenience method: fetches metadata, periods, and all declared localities in one call.

```python
agregado = client.get_agregado(1705)
# -> Agregado (with .periodos and .localidades populated)
```

#### `get_acervo(acervo)`

Fetches an "acervo" (collection) listing. Use `AcervoEnum` to select the desired collection.

```python
from sidra_fetcher.agregados import AcervoEnum

assuntos = client.get_acervo(AcervoEnum.ASSUNTO)
variaveis = client.get_acervo(AcervoEnum.VARIAVEL)
```

Available `AcervoEnum` values:

| Member              | Description            |
|---------------------|------------------------|
| `ASSUNTO`           | Topics / subjects      |
| `CLASSIFICACAO`     | Classifications        |
| `NIVELTERRITORIAL`  | Territorial levels     |
| `PERIODO`           | Periods                |
| `PERIODICIDADE`     | Periodicities          |
| `VARIAVEL`          | Variables              |

---

### `AsyncSidraClient` (asynchronous)

Drop-in async counterpart of `SidraClient`. All methods are coroutines. `get_agregado` fetches metadata and periods concurrently via `asyncio.gather`.

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

## Period Parsing

`get_agregado_periodos` parses the literal period strings returned by the API into structured `Periodo` objects. The detected frequency and computed date range are populated automatically.

### `Periodo` fields

| Field         | Type            | Description                                              |
|---------------|-----------------|----------------------------------------------------------|
| `id`          | `str`           | Raw period id from the API (e.g. `"202312"`)             |
| `literals`    | `list[str]`     | Human-readable representations (e.g. `["dezembro de 2023"]`) |
| `modificacao` | `dt.date`       | Date the period data was last updated                    |
| `frequencia`  | `str \| None`   | Detected frequency type (see table below)                |
| `data_inicio` | `dt.date \| None` | First day of the period                                |
| `data_fim`    | `dt.date \| None` | Last day of the period                                 |
| `ano`         | `int \| None`   | Year                                                     |
| `mes`         | `int \| None`   | Month (1–12); for rolling quarters, the last month       |
| `trimestre`   | `int \| None`   | Quarter number (1–4)                                     |
| `semestre`    | `int \| None`   | Semester number (1–2)                                    |
| `ano_fim`     | `int \| None`   | End year for multi-annual periods                        |

### Frequency types

| `frequencia`        | Literal example              | Date range                    |
|---------------------|------------------------------|-------------------------------|
| `mensal`            | `"janeiro de 2023"`          | Jan 1 – Jan 31                |
| `trimestral`        | `"1º trimestre de 2023"`     | Jan 1 – Mar 31                |
| `trimestre_movel`   | `"jan-fev-mar 2023"`         | Jan 1 – Mar 31                |
| `semestral`         | `"1º semestre de 2023"`      | Jan 1 – Jun 30                |
| `anual`             | `"2023"`                     | Jan 1 – Dec 31                |
| `plurianual`        | `"2020/2023"`                | Jan 1 2020 – Dec 31 2023      |
| `nao_reconhecida`   | *(unmatched)*                | `None` / `None`               |

The frequency constants are also importable:

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

## SIDRA API — URL Builder

The `Parametro` class builds and parses SIDRA `/values` request URLs.

```python
from sidra_fetcher.sidra import Parametro, Formato, Precisao

params = Parametro(
    agregado="1705",
    territorios={"3": ["all"]},   # all states
    variaveis=["4099"],            # unemployment rate
    periodos=["202301", "202302"],
    classificacoes={"2": ["6794"]},
    formato=Formato.A,
    decimais={"": Precisao.M},
)

print(params.url())
# https://apisidra.ibge.gov.br/values/t/1705/n3/all/v/4099/p/202301,202302/c2/6794/h/y/f/a/d/m
```

### `Parametro` parameters

| Parameter       | Type                        | SIDRA segment    | Example value                        |
|-----------------|-----------------------------|------------------|--------------------------------------|
| `agregado`      | `str`                       | `/t/{id}`        | `"1705"`                             |
| `territorios`   | `dict[str, list[str]]`      | `/n{level}/{ids}`| `{"3": ["all"]}` → `/n3/all`         |
| `variaveis`     | `list[str]`                 | `/v/{ids}`       | `["4099", "4100"]` or `[]` → `/v/all`|
| `periodos`      | `list[str]`                 | `/p/{ids}`       | `["202301"]` or `[]` → `/p/all`      |
| `classificacoes`| `dict[str, list[str]]`      | `/c{id}/{values}`| `{"2": ["6794"]}`                    |
| `cabecalho`     | `bool`                      | `/h/y` or `/h/n` | `True`                               |
| `formato`       | `Formato`                   | `/f/{code}`      | `Formato.A`                          |
| `decimais`      | `dict[str, Precisao]`       | `/d/{precision}` | `{"": Precisao.M}` → `/d/m`          |

### Parsing an existing SIDRA URL

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

## Reader and Flattening Utilities

### Saving and loading aggregate metadata

```python
from sidra_fetcher.reader import save_agregado, load_agregado

# Save to JSON
save_agregado(agregado, "agregado_1705.json")

# Load from JSON (periodos are re-parsed automatically)
agregado = load_agregado("agregado_1705.json")
```

### Flattening metadata for analysis

`flatten_aggregate_metadata` turns the hierarchical variable × classification structure into a flat sequence of dicts — one row per unique variable + category combination:

```python
from sidra_fetcher.reader import flatten_aggregate_metadata

raw_meta = client.get("https://servicodados.ibge.gov.br/api/v3/agregados/1705/metadados")

for row in flatten_aggregate_metadata(raw_meta):
    print(row["agregado"], row["D4N"], row.get("C5N"), row["MN"])
```

Each row contains:

| Key         | Description                                     |
|-------------|-------------------------------------------------|
| `agregado`  | Aggregate name                                  |
| `pesquisa`  | Survey name                                     |
| `assunto`   | Subject / topic                                 |
| `frequencia`| Frequency of the aggregate                      |
| `url_agregado` | Aggregate URL                                |
| `D4C`/`D4N` | Variable id / name                             |
| `D5C`/`D5N` | First classification id / name                 |
| `C5C`/`C5N` | First category id / name                       |
| `MN`        | Measurement unit                                |
| `nivel`     | Category hierarchy level                        |

`flatten_surveys_metadata` flattens the top-level survey index into a list of `{pesquisa_id, pesquisa, agregado_id, agregado}` dicts:

```python
from sidra_fetcher.reader import flatten_surveys_metadata

raw_index = client.get("https://servicodados.ibge.gov.br/api/v3/agregados")
rows = flatten_surveys_metadata(raw_index)
```

---

## Size and Statistics Utilities

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
#   "period_size": 54,    # rows per period
#   "total_size": 4536,   # estimated total rows
#   ...
# }
```

---

## Data Structures

Key dataclasses from `sidra_fetcher.agregados`:

```
Agregado
├── id, nome, url, assunto
├── pesquisa: Pesquisa (id, nome)
├── periodicidade: Periodicidade (frequencia, inicio, fim)
├── nivel_territorial: AgregadoNivelTerritorial
│   ├── administrativo: list[str]
│   ├── especial: list[str]
│   └── ibge: list[str]
├── variaveis: list[Variavel] (id, nome, unidade, sumarizacao)
├── classificacoes: list[Classificacao]
│   ├── id, nome
│   ├── sumarizacao: ClassificacaoSumarizacao (status, excecao)
│   └── categorias: list[Categoria] (id, nome, unidade, nivel)
├── periodos: list[Periodo]
│   └── id, literals, modificacao, frequencia,
│       data_inicio, data_fim, ano, mes, trimestre, semestre, ano_fim
└── localidades: list[Localidade]
    └── id, nome, nivel: NivelTerritorial (id, nome)
```

---

## Project Structure

```
src/sidra_fetcher/
├── __init__.py          — package logger
├── agregados.py         — dataclasses and URL builders for the Agregados API
├── fetcher.py           — SidraClient and AsyncSidraClient
├── periodos.py          — period string parsing and frequency detection
├── reader.py            — JSON → dataclass parsers and metadata flattening
├── sidra.py             — SIDRA URL builder (Parametro) and parsers
├── stats.py             — size and dimension statistics
└── api_undocumented.py  — URLs for undocumented IBGE endpoints
```

---

## Supported APIs

| API | Documentation |
|-----|---------------|
| IBGE Agregados v3 | https://servicodados.ibge.gov.br/api/docs/agregados?versao=3 |
| SIDRA | https://apisidra.ibge.gov.br/home/ajuda |

### Undocumented Acervos (Agregados)

| Acervo | URL |
|--------|-----|
| Assuntos | https://servicodados.ibge.gov.br/api/v3/agregados?acervo=A |
| Classificações | https://servicodados.ibge.gov.br/api/v3/agregados?acervo=C |
| Nível Territorial | https://servicodados.ibge.gov.br/api/v3/agregados?acervo=N |
| Períodos | https://servicodados.ibge.gov.br/api/v3/agregados?acervo=P |
| Periodicidades | https://servicodados.ibge.gov.br/api/v3/agregados?acervo=E |
| Variáveis | https://servicodados.ibge.gov.br/api/v3/agregados?acervo=V |

---

## Development

```bash
git clone https://github.com/dankkom/sidra-fetcher.git
cd sidra-fetcher
uv sync --extra dev
```

### Linting and formatting

```bash
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

### Running tests

```bash
uv run python -m unittest discover -v tests
```

---

## License

MIT. See [LICENSE](LICENSE) for details.
