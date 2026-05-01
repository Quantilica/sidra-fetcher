# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Helpers and dataclasses for the IBGE "agregados" API.

This module defines lightweight dataclasses that mirror the structure
returned by the IBGE agregados metadata endpoints and provides small
URL builder helpers to access the agregados API (index, metadata,
periods, localidades and acervos).

The dataclasses are intentionally minimal and used primarily as type
containers for data downloaded by :class:`sidra_fetcher.fetcher.SidraClient`.
"""

import datetime as dt
import urllib.parse as urlparse
from dataclasses import asdict, dataclass
from enum import StrEnum
from urllib.parse import urlencode

BASE_URL = "https://servicodados.ibge.gov.br/api/v3/agregados"


@dataclass
class Periodo:
    """Represents a period available for an aggregate.

    Attributes:
        id: Period identifier as provided by the API.
        literals: Human readable representations for the period.
        modificacao: Date when the period was last modified.
        frequencia: Detected frequency type (e.g., 'monthly', 'quarterly').
            Optional; populated by temporal parsing.
        data_inicio: Computed start datetime of the period.
            Optional; populated by temporal parsing.
        data_fim: Computed end datetime of the period.
            Optional; populated by temporal parsing.
        ano: Extracted year component. Optional; populated by temporal parsing.
        mes: Extracted month component (1-12). Optional.
        trimestre: Extracted quarter component (1-4). Optional.
        semestre: Extracted semester component (1-2). Optional.
        ano_fim: End year for multi-year periods. Optional.
    """

    id: str
    literals: list[str]
    modificacao: dt.date
    frequencia: str | None = None
    data_inicio: dt.datetime | None = None
    data_fim: dt.datetime | None = None
    ano: int | None = None
    mes: int | None = None
    trimestre: int | None = None
    semestre: int | None = None
    ano_fim: int | None = None


@dataclass
class NivelTerritorial:
    """Territorial level metadata (e.g. state, municipality).

    Attributes:
        id: Identifier for the territorial level.
        nome: Display name for the level.
    """

    id: str
    nome: str


@dataclass
class Localidade:
    """Represents a locality returned by the agregados API.

    Attributes:
        id: Locality identifier.
        nome: Locality name.
        nivel: The territorial level for this locality.
    """

    id: str
    nome: str
    nivel: NivelTerritorial


@dataclass
class Variavel:
    """Metadata for a variable available in an aggregate.

    Attributes:
        id: Variable identifier.
        nome: Variable name.
        unidade: Unit of measure.
        sumarizacao: Supported summarization modes for the variable.
    """

    id: int
    nome: str
    unidade: str
    sumarizacao: list[str]


@dataclass
class Categoria:
    """Represents a category/member of a classification.

    Attributes:
        id: Category identifier.
        nome: Category name.
        unidade: Optional unit of measure for this category.
        nivel: Category level (depth) within the classification.
    """

    id: int
    nome: str
    unidade: str | None
    nivel: int


@dataclass
class ClassificacaoSumarizacao:
    """Summarization configuration for a classification.

    Attributes:
        status: Whether summarization is enabled.
        excecao: List of category ids excluded from summarization.
    """

    status: bool
    excecao: list[int]


@dataclass
class Classificacao:
    """Classification metadata including available categories.

    Attributes:
        id: Classification identifier.
        nome: Display name.
        sumarizacao: Summarization rules.
        categorias: List of available categories.
    """

    id: int
    nome: str
    sumarizacao: ClassificacaoSumarizacao
    categorias: list[Categoria]


@dataclass
class Pesquisa:
    """Reference to the survey/research associated with the aggregate.

    Attributes:
        id: Survey identifier.
        nome: Survey name.
    """

    id: str
    nome: str


@dataclass
class Periodicidade:
    """Periodicidade metadata for an aggregate.

    Attributes:
        frequencia: Frequency id or description.
        inicio: Start of the supported period range.
        fim: End of the supported period range.
    """

    frequencia: str
    inicio: str
    fim: str


@dataclass
class AgregadoNivelTerritorial:
    """Lists of territorial levels used by an aggregate.

    Attributes:
        administrativo: Administrative territorial levels.
        especial: Special territorial levels.
        ibge: IBGE-specific territorial levels.
    """

    administrativo: list[str]
    especial: list[str]
    ibge: list[str]


@dataclass
class Agregado:
    """Complete metadata for an agregados API aggregate.

    Attributes mirror the structure returned by the IBGE agregados
    metadata endpoints and include variables, classifications,
    supported periods and localidades.
    """

    id: int
    nome: str
    url: str
    pesquisa: Pesquisa
    assunto: str
    periodicidade: Periodicidade
    nivel_territorial: AgregadoNivelTerritorial
    variaveis: list[Variavel]
    classificacoes: list[Classificacao]
    periodos: list[Periodo]
    localidades: list[Localidade]

    def asdict(self) -> dict:
        return asdict(self)


@dataclass
class IndiceAgregado:
    """Small index entry identifying an agregado within a pesquisa.

    Attributes:
        id: Aggregate id.
        nome: Aggregate name.
    """

    id: int
    nome: str


@dataclass
class IndicePesquisaAgregados:
    """Index of agregados grouped under a pesquisa/survey.

    Attributes:
        id: Survey id.
        nome: Survey name.
        agregados: List of :class:`IndiceAgregado` entries.
    """

    id: str
    nome: str
    agregados: list[IndiceAgregado]


class AcervoEnum(StrEnum):
    ASSUNTO = "A"
    CLASSIFICACAO = "C"
    NIVELTERRITORIAL = "N"
    PERIODO = "P"
    PERIODICIDADE = "E"
    VARIAVEL = "V"

    """Enum used to request different acervos (collections) from the API.

    Values correspond to the query parameter accepted by the
    agregados API (see `acervo` parameter in the API docs).
    """


def build_url_agregados() -> str:
    """Return the base URL for listing agregados grouped by pesquisa.

    Returns:
        The absolute URL to request the agregados index.
    """
    return BASE_URL


def build_url_metadados(agregado_id: int) -> str:
    """Return the metadata URL for a given agregado id.

    Args:
        agregado_id: Aggregate id to build the metadata URL for.

    Returns:
        Absolute URL for the aggregate metadata endpoint.
    """
    return BASE_URL + f"/{agregado_id}/metadados"


def build_url_periodos(agregado_id: int) -> str:
    """Return the periods URL for a given agregado id.

    Args:
        agregado_id: Aggregate id to query periods for.

    Returns:
        Absolute URL for the aggregate periods endpoint.
    """
    return BASE_URL + f"/{agregado_id}/periodos"


def build_url_localidades(agregado_id: int, localidades_nivel: str) -> str:
    """Return the localidades URL for an aggregate and territorial level.

    Args:
        agregado_id: Aggregate id.
        localidades_nivel: Comma-separated territorial level ids.

    Returns:
        Absolute URL for the localidades endpoint filtered by levels.
    """
    return BASE_URL + f"/{agregado_id}/localidades/{localidades_nivel}"


def build_url_acervos(acervo: AcervoEnum) -> str:
    """Return the base agregados URL with the ``acervo`` query parameter.

    Args:
        acervo: One of the :class:`AcervoEnum` members to request.

    Returns:
        Absolute URL with the acervo query parameter set.
    """
    params = {"acervo": acervo.value}
    url_parts = list(urlparse.urlparse(BASE_URL))
    query = dict(urlparse.parse_qsl(url_parts[4]))
    query.update(params)
    url_parts[4] = urlencode(query)
    return urlparse.urlunparse(url_parts)
