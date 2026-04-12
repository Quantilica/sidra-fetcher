# Copyright (C) 2022-2026 Daniel Kiyoyudi Komesu
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.


"""HTTP helpers to fetch metadata and data from IBGE's APIs.

This module provides a small :class:`SidraClient` wrapper around
``httpx`` used to download agregados indices, metadata, periods and
localidades as Python dataclasses defined in
``sidra_fetcher.api.agregados``.

The client includes retry logic on higher-level methods and returns
typed structures suitable for further processing by the package.
"""

import asyncio
import json
import time
from typing import Any

import httpx
from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_exponential

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
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)

    def get(self, url: str) -> Any:
        """Fetch data from the given URL.
        Args:
            url (str): The URL to fetch data from.
        Returns:
            Any: The data fetched from the URL, parsed as JSON.
        Raises:
            ConnectionError: If the data returned is None or if the request fails.
        """
        logger.info(f"Downloading DATA {url}")
        t0 = time.time()
        data = b""
        with self.client.stream("GET", url) as r:
            r.raise_for_status()
            for chunk in r.iter_bytes():
                data += chunk
        if not data:
            raise ConnectionError("Data returned is None!")
        t1 = time.time()
        logger.debug(f"Download of {url} took {t1 - t0:.2f} seconds")
        data = json.loads(data.decode("utf-8"))
        return data

    @retry(stop=stop_after_attempt(3))
    def get_indice_pesquisas_agregados(self) -> list[IndicePesquisaAgregados]:
        """Fetch the index of agregados grouped by pesquisa.

        Returns:
            A list of :class:`IndicePesquisaAgregados` objects representing
            the surveys and their contained agregados.
        Raises:
            ConnectionError: If downloading or parsing the response fails.
        """
        url_agregados = build_url_agregados()
        logger.info(f"Downloading list of agregados metadata {url_agregados}")
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

    @retry(stop=stop_after_attempt(3))
    def get_agregado_metadados(self, agregado_id: int) -> Agregado:
        """Fetch metadata for a specific agregado.

        Args:
            agregado_id: Numeric id of the aggregate to request.

        Returns:
            An :class:`Agregado` populated with metadata fields (variables,
            classifications, periodicidade and territorial levels).

        Raises:
            ConnectionError: If the HTTP request fails or the response is invalid.
        """
        url_metadados = build_url_metadados(agregado_id)
        logger.info(f"Downloading agregado metadados {url_metadados}")
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=3, max=30),
    )
    def get_agregado_periodos(self, agregado_id: int) -> list[Periodo]:
        """Fetch available periods for an aggregate.

        Args:
            agregado_id: Aggregate id to query periods for.

        Returns:
            A list of :class:`Periodo` objects parsed from the API response.
        """
        url_periodos = build_url_periodos(agregado_id)
        logger.info(f"Downloading agregado periodos {url_periodos}")
        raw_data = self.get(url_periodos)
        parsed_data = read_periodos(raw_data)
        return parsed_data

    def get_agregado_localidades(
        self, agregado_id: int, localidades_nivel: str
    ) -> list[Localidade]:
        """Fetch localidades for an aggregate filtered by territorial levels.

        Args:
            agregado_id: Aggregate id.
            localidades_nivel: Comma separated territorial level ids to request.

        Returns:
            A list of :class:`Localidade` objects.
        """
        url_localidades = build_url_localidades(agregado_id, localidades_nivel)
        logger.info(f"Downloading agregado localidades {url_localidades}")
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
        """Fetch a complete :class:`Agregado` including periods and localidades.

        This method composes the full aggregate metadata by calling the
        lower-level helpers to retrieve metadados, periods and all
        declared localidades for the aggregate's territorial levels.

        Args:
            agregado_id: Aggregate id to fetch.

        Returns:
            The populated :class:`Agregado` object.
        """
        logger.info(f"Downloading agregado {agregado_id}")
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
        """Fetch an `acervo` (collection) listing from the agregados API.

        Args:
            acervo: Member of :class:`AcervoEnum` identifying which collection
                to request (e.g. topics, variables, periods).

        Returns:
            The parsed JSON response from the API for the requested acervo.
        """
        url_acervo = build_url_acervos(acervo)
        logger.info(f"Downloading acervo {url_acervo}")
        data = self.get(url_acervo)
        return data

    def __enter__(self) -> "SidraClient":
        """Context manager enter: return the client instance."""
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Context manager exit: close underlying httpx client.

        Any exception handling is propagated; this method ensures the
        underlying client is closed and logs the shutdown.
        """
        if hasattr(self.client, "close"):
            self.client.close()
        else:
            logger.warning("Client does not have a close method.")
        logger.info("Fetcher closed.")


class AsyncSidraClient:
    """Async HTTP client for interacting with IBGE's agregados and SIDRA APIs.

    Drop-in async counterpart of :class:`SidraClient`.  Uses
    ``httpx.AsyncClient`` so all methods are coroutines and can be
    awaited concurrently (e.g. with ``asyncio.gather``).

    Use as an async context manager::

        async with AsyncSidraClient() as client:
            data = await client.get(url)
    """

    def __init__(self, timeout: int = 60) -> None:
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    async def get(self, url: str) -> Any:
        """Fetch data from the given URL asynchronously.

        Args:
            url: The URL to fetch data from.

        Returns:
            The data fetched from the URL, parsed as JSON.

        Raises:
            ConnectionError: If the data returned is empty or the request fails.
        """
        logger.info(f"Downloading DATA {url}")
        t0 = time.time()
        data = b""
        async with self.client.stream("GET", url) as r:
            r.raise_for_status()
            async for chunk in r.aiter_bytes():
                data += chunk
        if not data:
            raise ConnectionError("Data returned is None!")
        t1 = time.time()
        logger.debug(f"Download of {url} took {t1 - t0:.2f} seconds")
        return json.loads(data.decode("utf-8"))

    @retry(stop=stop_after_attempt(3))
    async def get_indice_pesquisas_agregados(
        self,
    ) -> list[IndicePesquisaAgregados]:
        """Fetch the index of agregados grouped by pesquisa."""
        url_agregados = build_url_agregados()
        logger.info(f"Downloading list of agregados metadata {url_agregados}")
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

    @retry(stop=stop_after_attempt(3))
    async def get_agregado_metadados(self, agregado_id: int) -> Agregado:
        """Fetch metadata for a specific agregado."""
        url_metadados = build_url_metadados(agregado_id)
        logger.info(f"Downloading agregado metadados {url_metadados}")
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=3, max=30),
    )
    async def get_agregado_periodos(self, agregado_id: int) -> list[Periodo]:
        """Fetch available periods for an aggregate."""
        url_periodos = build_url_periodos(agregado_id)
        logger.info(f"Downloading agregado periodos {url_periodos}")
        raw_data = await self.get(url_periodos)
        parsed_data = read_periodos(raw_data)
        return parsed_data

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=3, max=30),
    )
    async def get_agregado_localidades(
        self, agregado_id: int, localidades_nivel: str
    ) -> list[Localidade]:
        """Fetch localidades for an aggregate filtered by territorial level."""
        url_localidades = build_url_localidades(agregado_id, localidades_nivel)
        logger.info(f"Downloading agregado localidades {url_localidades}")
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
        """Fetch a complete :class:`Agregado` including periods and localidades.

        Metadados and periods are fetched concurrently.  Localidades for
        all territorial levels are also requested concurrently via
        ``asyncio.gather``.
        """
        logger.info(f"Downloading agregado {agregado_id}")
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
        logger.info(f"Downloading acervo {url_acervo}")
        return await self.get(url_acervo)

    async def __aenter__(self) -> "AsyncSidraClient":
        """Async context manager enter: return the client instance."""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """Async context manager exit: close underlying httpx async client."""
        await self.client.aclose()
        logger.info("AsyncSidraClient closed.")
