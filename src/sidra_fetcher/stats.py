# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Utilities to compute statistics and size estimates for agregados.

This module provides small helper functions that operate on an
`:class:`Agregado` object (from ``sidra_fetcher.api.agregados``) and
return useful summaries used for planning downloads or analysing the
data shape. Available functions include:

- ``get_stat_localidades``: counts localidades per territorial level.
- ``get_n_dimensoes``: computes the product of category counts across
    classifications (i.e. total number of dimension combinations).
- ``calculate_aggregate``: returns a dictionary with several metrics
    and size estimates (period/locality/variable dimensions and totals).
"""

from collections.abc import Iterable
from functools import reduce
from typing import Any

from .agregados import Agregado


def estimate_values(
    n_localidades: int,
    n_variaveis: int,
    categoria_counts: Iterable[int],
    n_periodos: int,
) -> dict[str, int]:
    """Estimate the number of values a SIDRA query returns from plain counts.

    Unlike :func:`calculate_aggregate`, this helper does not require an
    :class:`Agregado` object — callers holding counts from another source
    (e.g. a database) can reuse the same arithmetic.

    Args:
        n_localidades: Total number of selected localities.
        n_variaveis: Number of selected variables.
        categoria_counts: Number of selected categories per classification
            (empty when no classification is crossed).
        n_periodos: Number of selected periods.

    Returns:
        A dictionary with ``n_dimensoes`` (product of category counts),
        ``period_size`` (values per period) and ``total_size``.
    """
    n_dimensoes = reduce(lambda x, y: x * y, categoria_counts, 1)
    period_size = n_localidades * n_variaveis * max(n_dimensoes, 1)
    total_size = period_size * n_periodos
    return {
        "n_dimensoes": n_dimensoes,
        "period_size": period_size,
        "total_size": total_size,
    }


def get_stat_localidades(agregado: Agregado) -> dict[str, int]:
    """Count localities per territorial level for an aggregate.

    Args:
        agregado: An :class:`Agregado` object containing `localidades`.

    Returns:
        A mapping from territorial level id to the number of localidades.
    """
    stat_localidades: dict[str, int] = {}
    for localidade in agregado.localidades:
        nivel_id = localidade.nivel.id
        if nivel_id not in stat_localidades:
            stat_localidades[nivel_id] = 0
        stat_localidades[nivel_id] += 1
    return stat_localidades


def get_n_dimensoes(agregado: Agregado) -> int:
    """Compute the product of category counts across classifications.

    Args:
        agregado: Aggregate whose classifications are used.

    Returns:
        The total number of unique dimension combinations (product of
        category counts). Returns 1 when there are no classifications.
    """
    n_dimensoes = reduce(
        lambda x, y: x * y,
        [len(classificacao.categorias) for classificacao in agregado.classificacoes],
        1,
    )
    return n_dimensoes


def calculate_aggregate(agregado: Agregado) -> dict[str, Any]:
    """Calculate size and basic statistics for an aggregate.

    Args:
        agregado: Aggregate metadata object.

    Returns:
        A dictionary with counts (localidades, variaveis, classificacoes),
        dimension and period sizes and estimated total result size.
    """
    stat_localidades = get_stat_localidades(agregado)
    n_localidades = sum(stat_localidades.values())

    n_niveis_territoriais = len(stat_localidades)
    n_variaveis = len(agregado.variaveis)
    n_classificacoes = len(agregado.classificacoes)
    n_periodos = len(agregado.periodos)
    estimate = estimate_values(
        n_localidades=n_localidades,
        n_variaveis=n_variaveis,
        categoria_counts=[len(c.categorias) for c in agregado.classificacoes],
        n_periodos=n_periodos,
    )
    n_dimensoes = estimate["n_dimensoes"]
    period_size = estimate["period_size"]
    total_size = estimate["total_size"]
    localidade_size = max(n_variaveis, 1) * max(n_dimensoes, 1)
    variavel_size = max(n_dimensoes, 1)
    return {
        "pesquisa_id": agregado.pesquisa.id,
        "agregado_id": agregado.id,
        "stat_localidades": stat_localidades,
        "n_niveis_territoriais": n_niveis_territoriais,
        "n_localidades": n_localidades,
        "n_variaveis": n_variaveis,
        "n_classificacoes": n_classificacoes,
        "n_dimensoes": n_dimensoes,
        "n_periodos": n_periodos,
        "period_size": period_size,
        "localidade_size": localidade_size,
        "variavel_size": variavel_size,
        "total_size": total_size,
    }
