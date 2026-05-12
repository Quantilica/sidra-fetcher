# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""HTTP helpers to fetch metadata and data from IBGE's APIs.

This module provides a small :class:`SidraClient` wrapper around
``httpx`` used to download agregados indices, metadata, periods and
localidades as Python dataclasses defined in
``sidra_fetcher.api.agregados``.

The client includes retry logic on higher-level methods and returns
typed structures suitable for further processing by the package.
"""

import asyncio
from typing import Any

from quantilica_core.http import AsyncHttpClient, HttpClient
from quantilica_core.logging import log_step

from . import logger
from .agregados import (
    AcervoEnum,
    Agregado,
    AgregadoNivelTerritorial,
    Categoria,
    Classificacao,
    ClassificacaoSumarizacao,
    IndiceAgregado,
    IndicePesquisaAgregados,
    Localidade,
    NivelTerritorial,
    Periodicidade,
    Periodo,
    Pesquisa,
    Variavel,
    build_url_acervos,
    build_url_agregados,
    build_url_localidades,
    build_url_metadados,
    build_url_periodos,
)
from .reader import read_periodos


class SidraClient:
    """HTTP client for interacting with IBGE's agregados and SIDRA APIs.

    The class provides convenience methods to fetch agregados index,
    metadata, periods and localidades and to build higher level
    aggregate objects from the API responses.
    """

    def __init__(self, timeout: int = 60) -> None:
        self.client = HttpClient(timeout=timeout)

    def get(self, url: str) -> Any:
        """Fetch data from the given URL."""
        return self.client.get_json(url)

    def get_indice_pesquisas_agregados(self) -> list[IndicePesquisaAgregados]:
        """Fetch the index of agregados grouped by pesquisa."""
        url_agregados = build_url_agregados()
        with log_step(logger, "fetch-indice-pesquisas"):
            data = self.get(url_agregados)
            data = [
                IndicePesquisaAgregados(
                    id=item["id"],
                    nome=item["nome"],
                    agregados=[
                        IndiceAgregado(
                            id=agregado["id"],
                            nome=agregado["nome"],
                        )
                        for agregado in item["agregados"]
                    ],
                )
                for item in data
            ]
            return data

    def get_agregado_metadados(self, agregado_id: int) -> Agregado:
        """Fetch metadata for a specific agregado."""
        url_metadados = build_url_metadados(agregado_id)
        with log_step(
            logger, "fetch-agregado-metadados", agregado_id=agregado_id
        ):
            data = self.get(url_metadados)
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

    def get_agregado_periodos(self, agregado_id: int) -> list[Periodo]:
        """Fetch available periods for an aggregate."""
        url_periodos = build_url_periodos(agregado_id)
        raw_data = self.get(url_periodos)
        parsed_data = read_periodos(raw_data)
        return parsed_data

    def get_agregado_localidades(
        self, agregado_id: int, localidades_nivel: str
    ) -> list[Localidade]:
        """Fetch localidades for an aggregate filtered by territorial levels."""
        url_localidades = build_url_localidades(agregado_id, localidades_nivel)
        data = self.get(url_localidades)
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

    def get_agregado(self, agregado_id: int) -> Agregado:
        """Fetch a complete :class:`Agregado` including periods and localidades."""
        with log_step(
            logger, "fetch-agregado-complete", agregado_id=agregado_id
        ):
            agregado_metadados = self.get_agregado_metadados(agregado_id)
            agregado_periodos = self.get_agregado_periodos(agregado_id)
            agregado_localidades: list[Localidade] = []
            for nivel in agregado_metadados.nivel_territorial.administrativo:
                localidades = self.get_agregado_localidades(agregado_id, nivel)
                agregado_localidades.extend(localidades)
            for nivel in agregado_metadados.nivel_territorial.especial:
                localidades = self.get_agregado_localidades(agregado_id, nivel)
                agregado_localidades.extend(localidades)
            for nivel in agregado_metadados.nivel_territorial.ibge:
                localidades = self.get_agregado_localidades(agregado_id, nivel)
                agregado_localidades.extend(localidades)
            agregado_metadados.periodos = agregado_periodos
            agregado_metadados.localidades = agregado_localidades
            return agregado_metadados

    def get_acervo(self, acervo: AcervoEnum) -> Any:
        """Fetch an `acervo` (collection) listing from the agregados API."""
        url_acervo = build_url_acervos(acervo)
        data = self.get(url_acervo)
        return data

    def __enter__(self) -> "SidraClient":
        """Context manager enter: return the client instance."""
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Context manager exit."""
        pass


class AsyncSidraClient:
    """Async HTTP client for interacting with IBGE's agregados and SIDRA APIs."""

    def __init__(self, timeout: int = 60) -> None:
        self.client = AsyncHttpClient(timeout=timeout)

    async def get(self, url: str) -> Any:
        """Fetch data from the given URL asynchronously."""
        return await self.client.get_json(url)

    async def get_indice_pesquisas_agregados(
        self,
    ) -> list[IndicePesquisaAgregados]:
        """Fetch the index of agregados grouped by pesquisa."""
        url_agregados = build_url_agregados()
        with log_step(logger, "fetch-indice-pesquisas-async"):
            data = await self.get(url_agregados)
            return [
                IndicePesquisaAgregados(
                    id=item["id"],
                    nome=item["nome"],
                    agregados=[
                        IndiceAgregado(
                            id=agregado["id"],
                            nome=agregado["nome"],
                        )
                        for agregado in item["agregados"]
                    ],
                )
                for item in data
            ]

    async def get_agregado_metadados(self, agregado_id: int) -> Agregado:
        """Fetch metadata for a specific agregado."""
        url_metadados = build_url_metadados(agregado_id)
        with log_step(
            logger, "fetch-agregado-metadados-async", agregado_id=agregado_id
        ):
            data = await self.get(url_metadados)
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
            return Agregado(
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

    async def get_agregado_periodos(self, agregado_id: int) -> list[Periodo]:
        """Fetch available periods for an aggregate."""
        url_periodos = build_url_periodos(agregado_id)
        raw_data = await self.get(url_periodos)
        parsed_data = read_periodos(raw_data)
        return parsed_data

    async def get_agregado_localidades(
        self, agregado_id: int, localidades_nivel: str
    ) -> list[Localidade]:
        """Fetch localidades for an aggregate filtered by territorial level."""
        url_localidades = build_url_localidades(agregado_id, localidades_nivel)
        data = await self.get(url_localidades)
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

    async def get_agregado(self, agregado_id: int) -> Agregado:
        """Fetch a complete :class:`Agregado` including periods and localidades."""
        with log_step(
            logger, "fetch-agregado-complete-async", agregado_id=agregado_id
        ):
            agregado_metadados, agregado_periodos = await asyncio.gather(
                self.get_agregado_metadados(agregado_id),
                self.get_agregado_periodos(agregado_id),
            )
            niveis = (
                agregado_metadados.nivel_territorial.administrativo
                + agregado_metadados.nivel_territorial.especial
                + agregado_metadados.nivel_territorial.ibge
            )
            localidades_lists = await asyncio.gather(
                *(
                    self.get_agregado_localidades(agregado_id, nivel)
                    for nivel in niveis
                )
            )
            agregado_localidades: list[Localidade] = [
                loc for locs in localidades_lists for loc in locs
            ]
            agregado_metadados.periodos = agregado_periodos
            agregado_metadados.localidades = agregado_localidades
            return agregado_metadados

    async def get_acervo(self, acervo: AcervoEnum) -> Any:
        """Fetch an `acervo` (collection) listing from the agregados API."""
        url_acervo = build_url_acervos(acervo)
        return await self.get(url_acervo)

    async def __aenter__(self) -> "AsyncSidraClient":
        """Async context manager enter: return the client instance."""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """Async context manager exit."""
        pass
