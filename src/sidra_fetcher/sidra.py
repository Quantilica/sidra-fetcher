# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Utilities for constructing and parsing SIDRA API URLs.

This module contains helpers to build SIDRA request URLs and parse
components from existing SIDRA URLs. It also exposes small enums used
to format requests and a ``Parametro`` helper class that models the
query parameters supported by the SIDRA ``/values`` endpoint.

References:
- https://apisidra.ibge.gov.br
- https://apisidra.ibge.gov.br/home/ajuda
"""

import re
from enum import Enum
from typing import Any

BASE_URL = "https://apisidra.ibge.gov.br/values"


class Formato(Enum):
    """Enum para os formatos de saída do SIDRA."""

    A = "a"  # Códigos e nomes dos descritores
    C = "c"  # Códigos dos descritores
    N = "n"  # Nomes dos descritores
    U = "u"  # Códigos e nomes dos descritores, com unidades de medida


class Precisao(Enum):
    """Enum para os formatos de precisão do SIDRA."""

    S = "s"  # Precisão padrão
    M = "m"  # Precisão máxima
    D0 = "0"  # Sem casas decimais
    D1 = "1"  # Uma casa decimal
    D2 = "2"  # Duas casas decimais
    D3 = "3"  # Três casas decimais
    D4 = "4"  # Quatro casas decimais
    D5 = "5"  # Cinco casas decimais
    D6 = "6"  # Seis casas decimais
    D7 = "7"  # Sete casas decimais
    D8 = "8"  # Oito casas decimais
    D9 = "9"  # Nove casas decimais
    D10 = "10"  # Dez casas decimais
    D11 = "11"  # Onze casas decimais
    D12 = "12"  # Doze casas decimais
    D13 = "13"  # Treze casas decimais
    D14 = "14"  # Quatorze casas decimais
    D15 = "15"  # Quinze casas decimais
    D16 = "16"  # Dezesseis casas decimais
    D17 = "17"  # Dezessete casas decimais
    D18 = "18"  # Dezoito casas decimais
    D19 = "19"  # Dezenove casas decimais
    D20 = "20"  # Vinte casas decimais


class Parametro:
    """Model container for SIDRA `/values` request parameters.

    The class stores the typical segments used by SIDRA requests
    (aggregate, territories, variables, periods, classifications,
    header flag, format and decimal precision) and can render a
    complete request URL via :meth:`url`.

    Attributes
        agregado: Aggregate/table identifier used in the `/t/` segment.
        territorios: Mapping of territorial levels to lists of ids.
        variaveis: List of variable identifiers for the `/v/` segment.
        periodos: List of period identifiers for the `/p/` segment.
        classificacoes: Mapping of classification ids to selected values.
        cabecalho: Whether to include the header (`/h/y`) in the request.
        formato: Output format (see :class:`Formato`).
        decimais: Dict mapping variable keys to :class:`Precisao` values.
    """

    # Agregado
    agregado: str
    # 1 => /t/1

    # Variáveis
    variaveis: list[str]
    # ["123", "1234"] => /v/123,1234
    # [] => /v/all
    # ["all"] => /v/all

    # Nível territorial
    territorios: dict[str, list[str]]
    # {"6": ["3304557", "3550308"]} => /n6/3304557,3550308
    # {"1": ["all"], "6": []} => /n1/all/n6/all

    # Períodos
    periodos: list[str]
    # ["201201", "201301-201312"] => /p/201201,201301-201312
    # [] => /p/all
    # ["all"] => /p/all

    # Classificações
    classificacoes: dict[str, list[str]]
    # {"1": ["123", "321"], "32": ["23"]} => /c1/123,321/c32/23
    # {"1": ["all"], "32": []} => /c1/all/c32/all

    # Cabeçalho (header)
    cabecalho: bool = True

    # Formato'
    # Padrão é "a" (códigos e nomes dos descritores)
    formato: Formato = Formato.A

    # Precisão
    # Padrão é precisão máxima
    decimais: dict[str, Precisao]
    # {"": Precisao.M} => /d/m

    def __init__(
        self,
        agregado: str,
        territorios: dict[str, list[str]],
        variaveis: list[str],
        periodos: list[str],
        classificacoes: dict[str, list[str]],
        cabecalho: bool = True,
        # Padrão é "a" (códigos e nomes dos descritores)
        formato: Formato = Formato.A,
        decimais: dict[str, Precisao] = None,
    ) -> None:
        if decimais is None:
            decimais = {"": Precisao.M}
        self.agregado = agregado
        self.territorios = territorios
        self.variaveis = variaveis
        self.periodos = periodos
        self.classificacoes = classificacoes
        self.cabecalho = cabecalho
        self.formato = formato
        self.decimais = decimais

    def assign(self, name: str, value: Any) -> "Parametro":
        """Return a shallow copy of this Parametro with one attribute replaced.

        This helper is used to derive a new parameter set from an
        existing one without mutating the original instance.

        Args:
            name: Attribute name to replace on the returned instance.
            value: New value for the attribute.

        Returns:
            A new :class:`Parametro` with the requested attribute set.
        """
        p = Parametro(
            agregado=self.agregado,
            territorios=self.territorios,
            variaveis=self.variaveis,
            periodos=self.periodos,
            classificacoes=self.classificacoes,
            cabecalho=self.cabecalho,
            formato=self.formato,
            decimais=self.decimais,
        )
        setattr(p, name, value)
        return p

    def url(self) -> str:
        """Render the full SIDRA `/values` request URL for these parameters.

        Returns the absolute URL including the base endpoint and all
        configured segments (aggregate, territories, variables,
        periods, classifications, header flag, format and decimals).
        """
        t = f"/t/{self.agregado}"  # Agregado

        n = ""
        for key, value in self.territorios.items():
            if len(value) > 0:
                n = n + f"/n{key}/" + ",".join(value)
            else:
                n = n + f"/n{key}/all"

        if len(self.variaveis) > 0:
            v = "/v/" + ",".join(self.variaveis)
        else:
            v = "/v/all"

        if len(self.periodos) > 0:
            p = "/p/" + ",".join(self.periodos)
        else:
            p = "/p/all"

        c = ""
        for key, value in self.classificacoes.items():
            if len(value) > 0:
                c = c + f"/c{key}/" + ",".join(value)
            else:
                c = c + f"/c{key}/all"

        if self.cabecalho:
            h = "/h/y"
        else:
            h = "/h/n"

        f = f"/f/{self.formato.value}"  # Formato

        if len(self.decimais) >= 2:
            d = "/d/" + ",".join(
                [f"v{key}%20{value.value}" for key, value in self.decimais.items()]
            )
        elif len(self.decimais) == 1:
            precisao = self.decimais.get("", Precisao.M)
            d = f"/d/{precisao.value}"
        else:
            d = f"/d/{Precisao.M.value}"

        return BASE_URL + t + n + v + p + c + h + f + d

    def __repr__(self) -> str:
        return self.url()

    def __str__(self) -> str:
        return self.url()

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, Parametro):
            return NotImplemented
        agregado = self.agregado == o.agregado
        territorios = self.territorios == o.territorios
        variaveis = self.variaveis == o.variaveis
        periodos = self.periodos == o.periodos
        classificacoes = self.classificacoes == o.classificacoes
        cabecalho = self.cabecalho == o.cabecalho
        formato = self.formato == o.formato
        decimais = self.decimais == o.decimais
        return (
            agregado
            and territorios
            and variaveis
            and periodos
            and classificacoes
            and cabecalho
            and formato
            and decimais
        )


def get_sidra_url_request_period(
    parameter: Parametro,
    period_id: int,
) -> str:
    """Return a SIDRA request URL for a single period.

    Given a :class:`Parametro` instance, return a URL where the
    ``periods`` segment is replaced with the provided ``period_id``.
    """
    p = parameter.assign("periods", [str(period_id)])
    url = p.url()
    return url


def parse_territories(url: str) -> tuple[list[str], dict[str, list[str]]]:
    """Parse the `/n` (territory) segments from a SIDRA URL.

    Args:
        url: A SIDRA request URL (or the path part) to parse.

    Returns:
        A tuple ``(matches, territories)`` where ``matches`` is a list
        of raw matched strings and ``territories`` maps territorial
        level ids to lists of selected ids (or ``['all']``).
    """
    n = re.findall(r"(\/n\d\/)(all|\d+(,\d+)*)", url)
    n = ["".join(g) for g in n]
    territories = {
        ter.strip("n"): select.split(",")
        for _, ter, select in [i.split("/") for i in n]
    }
    return n, territories


def parse_periods(url: str) -> tuple[str, list[str]]:
    """Parse the `/p` (periods) segment from a SIDRA URL.

    Returns a tuple ``(raw_match, periods)`` where ``raw_match`` is the
    matched segment string (or empty string if not present) and
    ``periods`` is a list of individual period identifiers.
    """
    p = re.search(r"/p/(all|(first|last(%20\d+|))|\d{6}(,\d{6})*)", url)
    if not p:
        return "", []
    p = p.group()
    periods = p.strip("/p").split(",")
    return p, periods


def parse_header(url: str) -> tuple[str, bool]:
    """Parse the `/h` (header) flag from a SIDRA URL.

    Returns a tuple ``(raw_match, show_header)`` where ``show_header``
    is ``True`` when the URL contains ``/h/y`` and ``False`` for
    ``/h/n``. If the segment is missing the returned ``raw_match`` is
    an empty string and ``show_header`` defaults to ``True``.
    """
    h = re.search(r"/h/(y|n)", url)
    if not h:
        return "", True
    h = h.group()
    return h, h.strip("/h") == "y"


def parse_format(url: str) -> tuple[str, Formato]:
    """Parse the `/f` (format) segment and return the matching
    :class:`Formato`.

    Returns a tuple ``(raw_match, formato_enum)``. If the segment is
    missing this returns an empty string and ``Formato.A`` as default.
    """
    f = re.search(r"/f/(a|c|n|u)", url)
    if not f:
        return "", Formato.A
    f = f.group()
    return f, Formato(f.strip("/f"))


def parse_decimal(url: str) -> tuple[str, dict[str, Precisao]]:
    """Parse the `/d` (decimals/precision) segment.

    Returns a tuple ``(raw_match, decimal_map)`` where ``decimal_map``
    maps variable keys (or empty string for the global precision) to
    :class:`Precisao` values.
    """
    d = re.search(r"\/d\/(?:v\d+%20\d+(?:,v\d+%20\d+)*|[ms])", url)
    if not d:
        return "", {}
    decimal = {}
    d = d.group()
    if d.strip("/d") == "m":
        # If the precision is "m", it means maximum precision
        return d, {"": Precisao.M}
    elif d.strip("/d") == "s":
        # If the precision is "s", it means standard precision
        return d, {"": Precisao.S}
    decimal = {
        i.split("%20")[0].strip("v"): Precisao(i.split("%20")[1])
        for i in d.strip("/d").split(",")
    }
    return d, decimal


def parse_variables(url: str) -> tuple[str, list[str]]:
    """Parse the `/v` (variables) segment and return the variable ids.

    Returns a tuple ``(raw_match, variables)`` where ``variables`` is a
    list of ids or the special values like ``['all']``.
    """
    v = re.search(r"(\/v\/)(all|allxp|\d+(,\d+)*)", url)
    if not v:
        return "", []
    variables = []
    v = v.group()
    variables = v.strip("/v").split(",")
    return v, variables


def parse_classifications(url: str) -> tuple[list[str], dict[str, list[str]]]:
    """Parse `/c` (classification) segments from a SIDRA URL.

    Returns a tuple ``(matches, classifications)`` where
    ``classifications`` maps classification ids to lists of selected
    category ids (or ``['all']``).
    """
    c = re.findall(r"(\/c\d+\/)(all|allxt|\d+(,\d+)*)", url)
    c = ["".join(g) for g in c]
    classifications = {
        cat.strip("c"): [select] for _, cat, select in [i.split("/") for i in c]
    }

    return c, classifications


def parse_aggregate(url: str) -> tuple[str, str]:
    """Parse the `/t` (aggregate/table) segment and return its id.

    Returns ``(raw_match, aggregate_id)``. If absent both return values
    are empty strings.
    """
    t = re.search(r"/t/\d+", url)
    if not t:
        return "", ""
    t = t.group()
    aggregate = t.strip("/t")
    return t, aggregate


def parse_url(url: str) -> dict[str, Any]:
    """Parse all known SIDRA URL segments and return a parameter map.

    The returned dict contains the raw matched segments and parsed
    structures for aggregate, territories, classifications, variables,
    header, format, decimals and periods.
    """
    url = url.replace(BASE_URL, "")  # Remove the base of the url

    t, aggregate = parse_aggregate(url)
    n, territories = parse_territories(url)
    c, classifications = parse_classifications(url)
    v, variables = parse_variables(url)
    h, header = parse_header(url)
    f, format_ = parse_format(url)
    d, decimal = parse_decimal(url)
    p, periods = parse_periods(url)

    return {
        "url": url,
        "t": t,
        "aggregate": aggregate,
        "n": n,
        "territories": territories,
        "c": c,
        "classifications": classifications,
        "v": v,
        "variables": variables,
        "h": h,
        "header": header,
        "f": f,
        "format": format_,
        "d": d,
        "decimal": decimal,
        "p": p,
        "periods": periods,
    }


def parameter_from_url(url: str) -> Parametro:
    """Given a URL, returns a Parametro object"""
    _, aggregate = parse_aggregate(url)
    _, territories = parse_territories(url)
    _, classifications = parse_classifications(url)
    _, variables = parse_variables(url)
    _, header = parse_header(url)
    _, format_ = parse_format(url)
    _, decimais = parse_decimal(url)
    _, periods = parse_periods(url)
    parameter = Parametro(
        agregado=aggregate,
        territorios=territories,
        variaveis=variables,
        periodos=periods,
        classificacoes=classifications,
        cabecalho=header,
        formato=format_,
        decimais=decimais,
    )
    return parameter
