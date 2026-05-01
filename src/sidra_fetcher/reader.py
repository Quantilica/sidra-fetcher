# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Data readers and metadata flattening utilities for IBGE agregados.

This module provides functions to parse and transform raw JSON data from the
IBGE agregados API into typed Python dataclasses. It includes utilities for:

- Reading and parsing aggregate metadata into :class:`Agregado` objects
- Reading period information into :class:`Periodo` lists
- Reading locality data into :class:`Localidade` lists
- Flattening nested metadata structures for easier analysis
- Generating cross-product metadata combinations from variables and classifications

The flattening functions are particularly useful for converting hierarchical
aggregate metadata into tabular formats suitable for data analysis, where each
row represents a unique combination of variable, classifications, and categories.

Typical usage:

    >>> from sidra_fetcher.reader import read_metadados, read_periodos
    >>> # Parse aggregate metadata
    >>> agregado = read_metadados(raw_metadata_dict)
    >>> # Parse periods
    >>> periodos = read_periodos(raw_periods_list)
    >>> # Flatten for analysis
    >>> flattened = list(flatten_aggregate_metadata(raw_metadata_dict))
"""

import datetime as dt
import json
from pathlib import Path
from typing import Any, Generator

from .agregados import (
    Agregado,
    AgregadoNivelTerritorial,
    Categoria,
    Classificacao,
    ClassificacaoSumarizacao,
    Localidade,
    NivelTerritorial,
    Periodicidade,
    Periodo,
    Pesquisa,
    Variavel,
)
from .periodos import parse_date, parse_period


class DateEncoder(json.JSONEncoder):
    """JSON encoder that converts dt.date to ISO 8601 string."""

    def default(self, obj):
        if isinstance(obj, dt.date):
            return obj.isoformat()
        return super().default(obj)


# -----------------------------------------------------------------------------
# AGGREGATE METADATA ==========================================================
# _____________________________________________________________________________
def _iter_classificacoes_metadata(
    aggregate_metadata: dict,
    metadata: dict,
    i: int = 0,
    n: int = 4,
) -> Generator[
    dict[Any | str, Any | int] | dict[Any | str, Any] | Any, None, None
]:
    """Recursively iterate through classifications to generate metadata combinations.

    This internal function traverses the classification hierarchy of an aggregate,
    generating all possible combinations of categories across multiple classification
    dimensions. Each yielded dictionary contains metadata for one unique combination.

    The function recursively processes each classification level, creating cartesian
    products of categories. For each category, it appends classification and category
    identifiers and names to the metadata dictionary using indexed keys (D4C, D4N,
    C4C, C4N for dimension 4, D5C, D5N, C5C, C5N for dimension 5, etc.).

    Args:
        aggregate_metadata: The complete aggregate metadata dictionary containing
            a 'classificacoes' key with a list of classification objects.
        metadata: The current metadata dictionary being built, containing fields
            like aggregate name, survey, subject, variable info, etc.
        i: Current classification index being processed (0-based). Defaults to 0.
        n: Current dimension number for key generation (4-based, as dimensions
            1-3 are reserved for other metadata). Defaults to 4.

    Yields:
        dict: Metadata dictionaries representing each valid category combination.
            Each dict includes:
            - All keys from the input metadata parameter
            - D{n}C: Classification ID for dimension n
            - D{n}N: Classification name for dimension n
            - C{n}C: Category ID for dimension n
            - C{n}N: Category name for dimension n
            - MN: Measurement unit (from category or inherited from variable)
            - nivel: Hierarchy level (only in final combinations)

    Note:
        Categories with no unit at the last classification level are skipped.
        If there are no classifications, yields the metadata with nivel=0.
    """
    if len(aggregate_metadata["classificacoes"]) == 0:
        yield metadata | {"nivel": 0}
        return
    classification = aggregate_metadata["classificacoes"][i]
    classification_id = classification["id"]
    classification_name = classification["nome"]
    is_last_classification = i == len(aggregate_metadata["classificacoes"]) - 1
    for category in classification["categorias"]:
        category_id = category["id"]
        category_name = category["nome"]

        if category["unidade"]:
            unit = category["unidade"]
        else:
            unit = metadata["MN"]

        if unit is None and is_last_classification:
            continue

        new_metadata = metadata | {
            "D{i}C".format(i=n): classification_id,
            "D{i}N".format(i=n): classification_name,
            "C{i}C".format(i=n): category_id,
            "C{i}N".format(i=n): category_name,
            "MN": unit,
        }

        if is_last_classification:
            level = category["nivel"]
            yield new_metadata | {"nivel": level}
        else:
            yield from _iter_classificacoes_metadata(
                aggregate_metadata,
                new_metadata,
                i + 1,
                n + 1,
            )


def _iter_variaveis_metadata(
    aggregate_metadata: dict,
    metadata: dict,
) -> Generator[
    dict[Any | str, Any | int] | dict[Any | str, Any] | Any, None, None
]:
    """Iterate through variables and generate metadata for each variable-classification combination.

    This internal function processes all variables in an aggregate's metadata,
    delegating to :func:`_iter_classificacoes_metadata` to generate the full
    cross-product of variables and their classification categories.

    For each variable, it creates a metadata dictionary with variable-specific
    fields (D4C for variable code, D4N for variable name, MN for unit) and then
    yields all classification combinations for that variable.

    Args:
        aggregate_metadata: The complete aggregate metadata dictionary containing
            a 'variaveis' key with a list of variable objects.
        metadata: Base metadata dictionary containing aggregate-level information
            such as aggregate name, survey, subject, frequency, and URL.

    Yields:
        dict: Metadata dictionaries for each variable-classification combination.
            Each includes:
            - All keys from the base metadata parameter
            - D4C: Variable ID (code)
            - D4N: Variable name
            - MN: Measurement unit (None if unit starts with "Vide categorias")
            - Additional classification keys from _iter_classificacoes_metadata

    Note:
        Variables with units starting with "Vide categorias" have their unit
        set to None, indicating the unit is defined at the category level.
    """
    for variable in aggregate_metadata["variaveis"]:
        variable_id = variable["id"]
        variable_name = variable["nome"]
        unit = variable["unidade"]
        if unit.startswith("Vide categorias"):
            unit = None
        yield from _iter_classificacoes_metadata(
            aggregate_metadata,
            metadata
            | {
                "D4C": variable_id,  # Código da Variável
                "D4N": variable_name,  # Nome da Variável
                "MN": unit,
            },
        )


def flatten_aggregate_metadata(
    aggregate_metadata: dict,
) -> Generator[
    dict[Any | str, Any | int] | dict[Any | str, Any] | Any, None, None
]:
    """Flatten hierarchical aggregate metadata into a sequence of flat dictionaries.

    This function transforms complex, nested aggregate metadata from the IBGE API
    into a flat, tabular structure suitable for data analysis. Each yielded dictionary
    represents one unique combination of variable and classification categories,
    forming a complete metadata record.

    The flattening process extracts aggregate-level information (name, survey, subject,
    frequency, URL) and combines it with every possible combination of variables and
    their associated classification categories, creating a denormalized view of the
    metadata.

    This is particularly useful for:
    - Creating lookup tables for data interpretation
    - Generating metadata catalogs
    - Building data dictionaries for analysis
    - Understanding the dimensional structure of aggregates

    Args:
        aggregate_metadata: A dictionary containing complete aggregate metadata
            as returned by the IBGE agregados API. Must include keys:
            - 'nome': Aggregate name
            - 'pesquisa': Survey name
            - 'assunto': Subject/topic
            - 'periodicidade': Dict with 'frequencia' key
            - 'URL': Aggregate URL
            - 'variaveis': List of variable objects
            - 'classificacoes': List of classification objects

    Yields:
        dict: Flattened metadata records, each containing:
            - agregado: Aggregate name
            - pesquisa: Survey name
            - assunto: Subject/topic
            - frequencia: Data collection frequency
            - url_agregado: URL to the aggregate
            - D4C, D4N: Variable code and name
            - D5C, D5N, C5C, C5N, ...: Classification and category codes/names
            - MN: Measurement unit
            - nivel: Hierarchy level

    Example:
        >>> metadata = {
        ...     'nome': 'População',
        ...     'pesquisa': 'Censo',
        ...     'assunto': 'Demografia',
        ...     'periodicidade': {'frequencia': 'anual'},
        ...     'URL': 'http://...',
        ...     'variaveis': [...],
        ...     'classificacoes': [...]
        ... }
        >>> for record in flatten_aggregate_metadata(metadata):
        ...     print(record['agregado'], record['D4N'])
    """
    aggregate_name = aggregate_metadata["nome"]
    survey = aggregate_metadata["pesquisa"]
    subject = aggregate_metadata["assunto"]
    frequency = aggregate_metadata["periodicidade"]["frequencia"]
    url = aggregate_metadata["URL"]
    metadata = {
        "agregado": aggregate_name,
        "pesquisa": survey,
        "assunto": subject,
        "frequencia": frequency,
        "url_agregado": url,
    }
    yield from _iter_variaveis_metadata(
        aggregate_metadata=aggregate_metadata,
        metadata=metadata,
    )


def flatten_surveys_metadata(
    surveys_metadata: list[dict[str, Any]],
) -> list[dict[str, str | int]]:
    """Flatten surveys metadata into a simple list of survey-aggregate pairs.

    This function transforms the hierarchical survey index (which contains surveys
    with nested aggregate lists) into a flat list where each element represents
    one survey-aggregate relationship. This makes it easier to iterate over all
    aggregates across all surveys.

    The function is useful for:
    - Creating aggregate inventories
    - Building survey-aggregate lookup tables
    - Generating aggregate selection lists
    - Bulk processing of all aggregates

    Args:
        surveys_metadata: A list of survey dictionaries as returned by the
            get_indice_pesquisas_agregados endpoint. Each survey dict must have:
            - 'id': Survey identifier
            - 'nome': Survey name
            - 'agregados': List of aggregate dicts, each with 'id' and 'nome'

    Returns:
        A list of dictionaries, each representing one survey-aggregate pair with:
            - pesquisa_id: Survey identifier (string or int)
            - pesquisa: Survey name (string)
            - agregado_id: Aggregate identifier (int)
            - agregado: Aggregate name (string)

    Example:
        >>> surveys = [
        ...     {'id': 'P1', 'nome': 'Census', 'agregados': [
        ...         {'id': 1, 'nome': 'Population'},
        ...         {'id': 2, 'nome': 'Housing'}
        ...     ]}
        ... ]
        >>> flattened = flatten_surveys_metadata(surveys)
        >>> len(flattened)
        2
        >>> flattened[0]
        {'pesquisa_id': 'P1', 'pesquisa': 'Census',
         'agregado_id': 1, 'agregado': 'Population'}
    """
    return [
        {
            "pesquisa_id": survey["id"],
            "pesquisa": survey["nome"],
            "agregado_id": agg["id"],
            "agregado": agg["nome"],
        }
        for survey in surveys_metadata
        for agg in survey["agregados"]
    ]


def read_metadados(data: dict[str, Any]) -> Agregado:
    """Parse raw aggregate metadata JSON into an Agregado dataclass instance.

    This function transforms the raw metadata dictionary returned by the IBGE
    agregados metadata endpoint into a fully-typed :class:`Agregado` object with
    all nested structures (territorial levels, variables, classifications, categories)
    properly instantiated as dataclasses.

    The function handles the conversion of:
    - Territorial level information into AgregadoNivelTerritorial
    - Variables list into Variavel instances
    - Classifications and their categories into nested Classificacao and Categoria objects
    - Survey information into Pesquisa objects
    - Periodicity data into Periodicidade objects

    Note that the returned Agregado will have empty lists for 'periodos' and
    'localidades' - these should be populated separately using :func:`read_periodos`
    and :func:`read_localidades`.

    Args:
        data: Raw metadata dictionary from the IBGE API containing keys:
            - 'id': Aggregate identifier (int or str)
            - 'nome': Aggregate name (str)
            - 'URL': Aggregate URL (str)
            - 'pesquisa': Survey name (str)
            - 'assunto': Subject/topic (str)
            - 'periodicidade': Dict with frequency info
            - 'nivelTerritorial': Dict with 'Administrativo', 'Especial', 'IBGE' keys
            - 'variaveis': List of variable dicts
            - 'classificacoes': List of classification dicts

    Returns:
        Agregado: A fully instantiated Agregado dataclass with typed nested structures.
            The periodos and localidades fields will be empty lists and should be
            populated separately if needed.

    Example:
        >>> raw_data = client.get_agregado_metadata(1705)
        >>> agregado = read_metadados(raw_data)
        >>> print(agregado.nome)
        >>> print(len(agregado.variaveis))
        >>> print(agregado.classificacoes[0].nome)
    """
    nivel_territorial = AgregadoNivelTerritorial(
        administrativo=data["nivelTerritorial"]["Administrativo"],
        especial=data["nivelTerritorial"]["Especial"],
        ibge=data["nivelTerritorial"]["IBGE"],
    )
    variaveis = [
        Variavel(
            id=v["id"],
            nome=v["nome"],
            unidade=v["unidade"],
            sumarizacao=v["sumarizacao"],
        )
        for v in data["variaveis"]
    ]
    classificacoes = [
        Classificacao(
            id=cla["id"],
            nome=cla["nome"],
            sumarizacao=ClassificacaoSumarizacao(
                status=cla["sumarizacao"]["status"],
                excecao=cla["sumarizacao"]["excecao"],
            ),
            categorias=[
                Categoria(
                    id=cat["id"],
                    nome=cat["nome"],
                    unidade=cat["unidade"],
                    nivel=cat["nivel"],
                )
                for cat in cla["categorias"]
            ],
        )
        for cla in data["classificacoes"]
    ]
    agregado = Agregado(
        id=data["id"],
        nome=data["nome"],
        url=data["URL"],
        pesquisa=Pesquisa(id="", nome=data["pesquisa"]),
        assunto=data["assunto"],
        periodicidade=Periodicidade(**data["periodicidade"]),
        nivel_territorial=nivel_territorial,
        variaveis=variaveis,
        classificacoes=classificacoes,
        periodos=[],
        localidades=[],
    )
    return agregado


def read_periodos(data: list[dict[str, Any]]) -> list[Periodo]:
    """Parse raw periods data into a list of Periodo dataclass instances.

    This function converts the raw period information returned by the IBGE
    agregados periods endpoint into typed :class:`Periodo` objects with
    enriched temporal metadata. It handles date parsing, temporal feature
    extraction (frequency, start/end dates, temporal components), and converts
    the modification date string from Brazilian format (dd/mm/yyyy) to a Python
    date object.

    Each period represents a time point or range for which data is available
    in the aggregate, along with metadata about when that period's data was
    last updated and its temporal structure.

    Args:
        data: A list of period dictionaries from the IBGE API, each containing:
            - 'id': Period identifier (str), e.g., '202301' for January 2023
            - 'literals': List of human-readable period representations (list[str])
            - 'modificacao': Last modification date as string in 'dd/mm/yyyy' format

    Returns:
        list[Periodo]: A list of Periodo instances with:
            - id, literals, modificacao (as per basic parsing)
            - frequencia: Detected frequency type (monthly, quarterly, etc.)
            - data_inicio: Computed start datetime
            - data_fim: Computed end datetime
            - ano, mes, trimestre, semestre, ano_fim: Extracted components

    Example:
        >>> raw_periods = client.get_agregado_periodos(1705)
        >>> periodos = read_periodos(raw_periods)
        >>> print(periodos[0].id)
        '202312'
        >>> print(periodos[0].literals)
        ['dezembro 2023', '12/2023']
        >>> print(periodos[0].modificacao)
        datetime.date(2024, 1, 15)
        >>> print(periodos[0].frequencia)
        'monthly'
        >>> print(periodos[0].ano, periodos[0].mes)
        2023 12
    """
    result = []
    for periodo in data:
        # Parse enriched temporal metadata
        parsed = parse_period(periodo)

        # Create Periodo with enriched fields
        p = Periodo(
            id=periodo["id"],
            literals=periodo["literals"],
            modificacao=parse_date(periodo["modificacao"]),
            frequencia=parsed.get("frequencia"),
            data_inicio=parsed.get("data_inicio"),
            data_fim=parsed.get("data_fim"),
            ano=parsed.get("ano"),
            mes=parsed.get("mes"),
            trimestre=parsed.get("trimestre"),
            semestre=parsed.get("semestre"),
            ano_fim=parsed.get("ano_fim"),
        )
        result.append(p)

    return result


def read_localidades(data: list[dict[str, Any]]) -> list[Localidade]:
    """Parse raw localities data into a list of Localidade dataclass instances.

    This function converts the raw locality information returned by the IBGE
    agregados localities endpoint into typed :class:`Localidade` objects. Each
    locality represents a geographic unit (municipality, state, region, etc.)
    for which data is available in the aggregate.

    The function properly instantiates the nested territorial level information
    as :class:`NivelTerritorial` objects, preserving the hierarchy and type of
    each geographic unit.

    Args:
        data: A list of locality dictionaries from the IBGE API, each containing:
            - 'id': Locality identifier (str), e.g., '3550308' for São Paulo city
            - 'nome': Locality name (str), e.g., 'São Paulo'
            - 'nivel': Dictionary with territorial level info:
                - 'id': Level identifier (str), e.g., 'N6' for municipality
                - 'nome': Level name (str), e.g., 'Município'

    Returns:
        list[Localidade]: A list of Localidade instances, each with:
            - id: Locality identifier
            - nome: Locality name
            - nivel: NivelTerritorial instance with id and nome fields

    Example:
        >>> raw_localities = client.get_agregado_localidades(1705, 'N6')
        >>> localidades = read_localidades(raw_localities)
        >>> print(localidades[0].nome)
        'São Paulo'
        >>> print(localidades[0].nivel.nome)
        'Município'
        >>> print(len(localidades))
        5570
    """
    return [
        Localidade(
            id=localidade["id"],
            nome=localidade["nome"],
            nivel=NivelTerritorial(
                id=localidade["nivel"]["id"],
                nome=localidade["nivel"]["nome"],
            ),
        )
        for localidade in data
    ]


def save_agregado(agregado: Agregado, path: str | Path) -> None:
    """Save an Agregado instance to a JSON file.

    Args:
        agregado: The Agregado instance to save.
        path: Path to the output JSON file.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            agregado.asdict(),
            f,
            ensure_ascii=False,
            indent=2,
            cls=DateEncoder,
        )


def load_agregado(path: str | Path) -> Agregado:
    """Load an Agregado instance from a JSON file.

    Args:
        path: Path to the input JSON file.

    Returns:
        The deserialized Agregado instance.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    nivel_territorial = AgregadoNivelTerritorial(**data["nivel_territorial"])
    pesquisa = Pesquisa(**data["pesquisa"])
    periodicidade = Periodicidade(**data["periodicidade"])

    variaveis = [Variavel(**v) for v in data.get("variaveis", [])]

    classificacoes = []
    for c in data.get("classificacoes", []):
        sumarizacao = ClassificacaoSumarizacao(**c["sumarizacao"])
        categorias = [Categoria(**cat) for cat in c.get("categorias", [])]
        classificacoes.append(
            Classificacao(
                id=c["id"],
                nome=c["nome"],
                sumarizacao=sumarizacao,
                categorias=categorias,
            )
        )

    periodos = read_periodos(data.get("periodos", []))

    localidades = []
    for loc in data.get("localidades", []):
        nivel = NivelTerritorial(**loc["nivel"])
        localidades.append(
            Localidade(
                id=loc["id"],
                nome=loc["nome"],
                nivel=nivel,
            )
        )

    return Agregado(
        id=data["id"],
        nome=data["nome"],
        url=data["url"],
        pesquisa=pesquisa,
        assunto=data["assunto"],
        periodicidade=periodicidade,
        nivel_territorial=nivel_territorial,
        variaveis=variaveis,
        classificacoes=classificacoes,
        periodos=periodos,
        localidades=localidades,
    )
