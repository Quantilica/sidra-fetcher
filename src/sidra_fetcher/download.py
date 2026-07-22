# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Download completo de dados de um agregado SIDRA, respeitando o limite da API.

Este módulo planeja (chunking) e executa o download de TODOS os dados de uma
tabela SIDRA (endpoint `/values`) a partir de um único ``agregado_id``,
dividindo a seleção completa em requisições que nunca excedem
``SIDRA_API_VALUES_LIMIT`` (100.000 valores). Ao contrário do ``sidra-sql``
(que assume que cada período isolado já cabe no limite — garantido
manualmente por quem escreve o pipeline), este módulo descobre e divide
automaticamente, priorizando nesta ordem: período -> lote de localidades ->
variável -> combinação de categorias de classificação.

Cada nível territorial do agregado (administrativo, especial, ibge) é
planejado e baixado separadamente — nunca combinado num único ``Parametro``.

Typical usage:

    >>> from sidra_fetcher.fetcher import SidraClient
    >>> with SidraClient() as client:
    ...     chunks = client.plan_dados_agregado(1705)
    ...     resumo = describe_download_plan(chunks)
    ...     paths = client.download_dados_agregado(1705, "./sidra_data")
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from quantilica.core.exceptions import FetchError
from quantilica.core.manifests import DownloadManifest

from .agregados import Agregado
from .sidra import SIDRA_API_VALUES_LIMIT, Formato, Parametro, Precisao

if TYPE_CHECKING:
    from .fetcher import SidraClient


class _RateLimiter:
    """Limitador de taxa thread-safe: garante ``min_interval`` segundos entre
    o início de requisições consecutivas, mesmo com vários workers.

    Reserva o próximo horário permitido sob lock (operação rápida) e dorme
    fora do lock, para que os workers não se serializem no sleep e a thread
    principal nunca fique bloqueada esperando o delay.
    """

    def __init__(self, min_interval: float) -> None:
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            alvo = max(now, self._next)
            self._next = alvo + self.min_interval
        espera = alvo - now
        if espera > 0:
            time.sleep(espera)


def _validar_linhas(url: str, linhas: object) -> list:
    """Garante que a resposta do SIDRA é uma lista de registros.

    A API às vezes responde HTTP 200 com um corpo de erro em formato de dict
    (``{"status": ..., "message": ...}``); sem esta checagem, o fatiamento
    ``linhas[1:]`` levantaria um ``TypeError`` obscuro no meio do download.
    """
    if not isinstance(linhas, list):
        raise FetchError(f"Resposta inesperada do SIDRA em {url}: {linhas!r:.200}")
    return linhas


@dataclass(frozen=True)
class DownloadChunk:
    """Um request planejado para o endpoint `/values` do SIDRA.

    Attributes:
        nivel_territorial: Nível territorial na forma da API de metadados
            (ex.: ``"N6"``).
        parametro: Parâmetros completos do request.
        n_valores: Estimativa exata de valores retornados por este chunk.
    """

    nivel_territorial: str
    parametro: Parametro
    n_valores: int


@dataclass(frozen=True)
class _Pools:
    """Pools completos (ou restritos pelo usuário) de ids para um nível territorial."""

    periodos: list[str]
    localidades: list[str]
    variaveis: list[str]
    classificacoes: dict[str, list[str]]


@dataclass(frozen=True)
class _PlanContext:
    """Seleção corrente durante o chunking.

    ``None`` num campo (ou por chave, em ``classificacoes``) significa "todo
    o pool", renderizado como o seletor ``all``/``[]`` do SIDRA — evita
    materializar listas gigantes (ex.: 5.570 municípios) quando o usuário só
    quer "todos".
    """

    periodos: list[str] | None = None
    localidades: list[str] | None = None
    variaveis: list[str] | None = None
    classificacoes: dict[str, list[str] | None] = field(default_factory=dict)


def _context_n_valores(ctx: _PlanContext, pools: _Pools) -> int:
    """Calcula o total de valores (produto das dimensões) de um contexto."""
    n_periodos = len(ctx.periodos) if ctx.periodos is not None else len(pools.periodos)
    n_localidades = (
        len(ctx.localidades) if ctx.localidades is not None else len(pools.localidades)
    )
    n_variaveis = (
        len(ctx.variaveis) if ctx.variaveis is not None else len(pools.variaveis)
    )
    n_dimensoes = 1
    for cid, pool_categorias in pools.classificacoes.items():
        selecionadas = ctx.classificacoes.get(cid)
        n_dimensoes *= (
            len(selecionadas) if selecionadas is not None else len(pool_categorias)
        )
    return n_periodos * n_localidades * n_variaveis * n_dimensoes


def _chunked(items: list[str], size: int) -> Generator[list[str], None, None]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _split_classificacoes(
    ctx: _PlanContext, pools: _Pools, limit: int
) -> Generator[_PlanContext, None, None]:
    """Fallback final: expande, uma categoria por vez, a classificação com
    mais categorias selecionadas atualmente — generalização de
    ``sidra_sql.sidra.unnest_classificacoes`` que para assim que o contexto
    cabe no limite, em vez de sempre expandir tudo.
    """
    if _context_n_valores(ctx, pools) <= limit:
        yield ctx
        return

    candidatos = [
        (
            cid,
            ctx.classificacoes.get(cid)
            if ctx.classificacoes.get(cid) is not None
            else pool_categorias,
        )
        for cid, pool_categorias in pools.classificacoes.items()
    ]
    if not candidatos:
        # Não há mais nenhuma dimensão para dividir; o chunk é atômico.
        yield ctx
        return

    cid, categorias = max(candidatos, key=lambda kv: len(kv[1]))
    if len(categorias) <= 1:
        yield ctx
        return

    for categoria in categorias:
        # Ao contrário de `sidra_sql.sidra.unnest_classificacoes` (que pula a
        # categoria "0"/"Total" porque pipelines curados só querem as
        # categorias granulares), aqui a categoria "0" é só mais um valor
        # retornado pela API e precisa ser baixada — omiti-la deixaria dados
        # faltando, contrariando o objetivo de baixar TUDO.
        nova_classificacoes = {**ctx.classificacoes, cid: [categoria]}
        yield from _split_classificacoes(
            replace(ctx, classificacoes=nova_classificacoes), pools, limit
        )


def _split_context(
    ctx: _PlanContext, pools: _Pools, limit: int
) -> Generator[_PlanContext, None, None]:
    """Divide recursivamente um contexto até que cada resultado caiba no limite.

    Ordem de prioridade: período -> lote de localidades -> variável ->
    combinação de classificações (via :func:`_split_classificacoes`).
    """
    if _context_n_valores(ctx, pools) <= limit:
        yield ctx
        return

    # 1) período
    periodos = ctx.periodos if ctx.periodos is not None else pools.periodos
    if len(periodos) > 1:
        for periodo in periodos:
            yield from _split_context(replace(ctx, periodos=[periodo]), pools, limit)
        return

    # 2) lote de localidades — calcula o maior lote que cabe no limite.
    localidades = ctx.localidades if ctx.localidades is not None else pools.localidades
    if len(localidades) > 1:
        tamanho_um = _context_n_valores(
            replace(ctx, localidades=[localidades[0]]), pools
        )
        tamanho_lote = max(1, limit // tamanho_um) if tamanho_um else len(localidades)
        for lote in _chunked(localidades, tamanho_lote):
            yield from _split_context(replace(ctx, localidades=lote), pools, limit)
        return

    # 3) variável
    variaveis = ctx.variaveis if ctx.variaveis is not None else pools.variaveis
    if len(variaveis) > 1:
        for variavel in variaveis:
            yield from _split_context(replace(ctx, variaveis=[variavel]), pools, limit)
        return

    # 4) combinação de classificações (fallback final)
    yield from _split_classificacoes(ctx, pools, limit)


def _context_to_parametro(
    agregado_id: int | str,
    nivel: str,
    ctx: _PlanContext,
    formato: Formato,
    decimais: dict[str, Precisao],
) -> Parametro:
    """Converte um ``_PlanContext`` resolvido em um ``Parametro`` de requisição.

    Nota: os níveis territoriais dos metadados usam a forma prefixada
    (``"N6"``), mas ``Parametro.territorios`` espera a chave numérica pura
    (``"6"``) — daí o ``removeprefix("N")``.
    """
    nivel_numero = nivel.removeprefix("N")
    return Parametro(
        agregado=str(agregado_id),
        territorios={nivel_numero: list(ctx.localidades) if ctx.localidades else []},
        variaveis=list(ctx.variaveis) if ctx.variaveis else [],
        periodos=list(ctx.periodos) if ctx.periodos else [],
        classificacoes={
            cid: (list(cats) if cats else [])
            for cid, cats in ctx.classificacoes.items()
        },
        formato=formato,
        decimais=decimais,
    )


def _niveis_territoriais_disponiveis(agregado: Agregado) -> list[str]:
    """Todos os níveis territoriais do agregado, na ordem administrativo,
    especial, ibge, sem duplicatas.
    """
    niveis: list[str] = []
    for nivel in (
        agregado.nivel_territorial.administrativo
        + agregado.nivel_territorial.especial
        + agregado.nivel_territorial.ibge
    ):
        if nivel not in niveis:
            niveis.append(nivel)
    return niveis


def _restringir_pool(
    nome: str, pool: list[str], escolhidos: list[str] | None
) -> list[str]:
    """Restringe ``pool`` à seleção do usuário, validando os ids.

    Retorna o pool completo quando ``escolhidos is None`` (sem restrição).
    Levanta ``ValueError`` se algum id escolhido não existe no agregado ou
    se a seleção resulta vazia — para uma tabela arbitrária, um filtro que
    não casa com nada deve falhar alto, não baixar tudo silenciosamente.
    """
    if escolhidos is None:
        return pool
    validos = set(pool)
    desconhecidos = [x for x in escolhidos if x not in validos]
    if desconhecidos:
        raise ValueError(f"{nome} inexistente(s) no agregado: {desconhecidos}")
    escolhidos_set = set(escolhidos)
    restrito = [x for x in pool if x in escolhidos_set]
    if not restrito:
        raise ValueError(f"Seleção de {nome} vazia após o filtro")
    return restrito


def plan_agregado_download(
    agregado: Agregado,
    *,
    niveis_territoriais: list[str] | None = None,
    variaveis: list[str] | None = None,
    periodos: list[str] | None = None,
    classificacoes: dict[str, list[str]] | None = None,
    formato: Formato = Formato.A,
    decimais: dict[str, Precisao] | None = None,
    limit: int = SIDRA_API_VALUES_LIMIT,
) -> list[DownloadChunk]:
    """Planeja os requests necessários para baixar todos os dados de um agregado.

    Por padrão, baixa todas as variáveis, períodos, classificações/categorias
    e níveis territoriais disponíveis no agregado. Cada nível territorial é
    planejado separadamente — nunca combinado num único ``Parametro``.

    Args:
        agregado: Metadados completos do agregado (com ``periodos`` e
            ``localidades`` já preenchidos, ex.: via ``SidraClient.get_agregado``).
        niveis_territoriais: Níveis a baixar (forma ``"N6"``). Padrão: todos
            os níveis disponíveis no agregado.
        variaveis: IDs de variáveis a restringir. Padrão: todas.
        periodos: IDs de períodos a restringir. Padrão: todos.
        classificacoes: Mapa de classificação -> categorias a restringir.
            Classificações omitidas usam todas as categorias. Padrão: todas.
        formato: Formato de saída do SIDRA (padrão ``Formato.A``).
        decimais: Precisão decimal (padrão precisão máxima).
        limit: Limite de valores por requisição (padrão ``SIDRA_API_VALUES_LIMIT``).

    Returns:
        Lista de :class:`DownloadChunk`, cobrindo exatamente a seleção pedida
        sem sobreposição e sem excesso, cada um respeitando ``limit``.
    """
    if decimais is None:
        decimais = {"": Precisao.M}

    disponiveis = _niveis_territoriais_disponiveis(agregado)
    if niveis_territoriais is not None:
        desconhecidos = [n for n in niveis_territoriais if n not in disponiveis]
        if desconhecidos:
            raise ValueError(
                f"Nível(is) territorial(is) inexistente(s) no agregado "
                f"{agregado.id}: {desconhecidos}"
            )
        niveis = niveis_territoriais
    else:
        niveis = disponiveis

    periodos_pool = _restringir_pool(
        "período(s)", [p.id for p in agregado.periodos], periodos
    )
    variaveis_pool = _restringir_pool(
        "variável(is)", [str(v.id) for v in agregado.variaveis], variaveis
    )

    classificacoes_pool: dict[str, list[str]] = {
        str(c.id): [str(cat.id) for cat in c.categorias]
        for c in agregado.classificacoes
    }
    if classificacoes is not None:
        desconhecidas = [c for c in classificacoes if c not in classificacoes_pool]
        if desconhecidas:
            raise ValueError(
                f"Classificação(ões) inexistente(s) no agregado "
                f"{agregado.id}: {desconhecidas}"
            )
        classificacoes_pool = {
            cid: _restringir_pool(
                f"categoria(s) da classificação {cid}",
                cats,
                classificacoes.get(cid),
            )
            for cid, cats in classificacoes_pool.items()
        }

    chunks: list[DownloadChunk] = []
    for nivel in niveis:
        localidades_pool = [
            loc.id for loc in agregado.localidades if loc.nivel.id == nivel
        ]
        if not localidades_pool:
            # Nível declarado nos metadados do agregado, mas sem nenhuma
            # localidade associada (acontece com alguns níveis "especiais")
            # — não há nada para baixar, então não geramos um request vazio.
            continue
        pools = _Pools(
            periodos=periodos_pool,
            localidades=localidades_pool,
            variaveis=variaveis_pool,
            classificacoes=classificacoes_pool,
        )
        # `None` num campo do contexto inicial só é seguro quando o usuário
        # NÃO restringiu aquela dimensão (pool == universo completo do
        # agregado) — nesse caso, "None" -> "all" é exatamente o que se
        # quer. Quando há restrição explícita, ela precisa ficar
        # materializada desde o início: se a seleção restrita já couber
        # num único chunk, o splitter nunca vai tocar esse campo, e
        # `_context_to_parametro` renderizaria "all" (todos os valores do
        # agregado) em vez da restrição pedida — perdendo o filtro.
        ctx_inicial = _PlanContext(
            periodos=list(periodos_pool) if periodos is not None else None,
            variaveis=list(variaveis_pool) if variaveis is not None else None,
            classificacoes={
                cid: (
                    list(cats)
                    if classificacoes is not None and cid in classificacoes
                    else None
                )
                for cid, cats in classificacoes_pool.items()
            },
        )
        for ctx in _split_context(ctx_inicial, pools, limit):
            parametro = _context_to_parametro(
                agregado.id, nivel, ctx, formato, decimais
            )
            chunks.append(
                DownloadChunk(
                    nivel_territorial=nivel,
                    parametro=parametro,
                    n_valores=_context_n_valores(ctx, pools),
                )
            )
    return chunks


def describe_download_plan(chunks: list[DownloadChunk]) -> dict[str, Any]:
    """Resumo de um plano de download: total de requests e valores estimados.

    Returns:
        Dict com ``n_requests``, ``n_valores`` e ``por_nivel`` (mapa de nível
        territorial para ``{"n_requests": int, "n_valores": int}``).
    """
    por_nivel: dict[str, dict[str, int]] = {}
    for chunk in chunks:
        resumo = por_nivel.setdefault(
            chunk.nivel_territorial, {"n_requests": 0, "n_valores": 0}
        )
        resumo["n_requests"] += 1
        resumo["n_valores"] += chunk.n_valores
    return {
        "n_requests": len(chunks),
        "n_valores": sum(c.n_valores for c in chunks),
        "por_nivel": por_nivel,
    }


def iter_download_chunks(
    client: SidraClient,
    chunks: list[DownloadChunk],
    *,
    politeness_delay: float = 0.0,
) -> Generator[tuple[DownloadChunk, list[dict]], None, None]:
    """Baixa os chunks sequencialmente, um de cada vez (sem threads).

    Seguro em memória (um chunk por vez) — apropriado para tabelas grandes
    ou quando concorrência não é necessária/desejada.
    """
    for i, chunk in enumerate(chunks):
        url = chunk.parametro.url()
        rows = _validar_linhas(url, client.get(url))
        yield chunk, rows
        if politeness_delay and i < len(chunks) - 1:
            time.sleep(politeness_delay)


def _download_nivel(
    client: SidraClient,
    grupo: list[DownloadChunk],
    target: Path,
    *,
    agregado_id: int,
    nivel: str,
    max_workers: int,
    politeness_delay: float,
    on_chunk_done: Callable[[DownloadChunk], None] | None,
) -> Path:
    """Baixa todos os chunks de um nível territorial e grava NDJSON + manifest."""
    fd, raw_temp_path = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temp_path = Path(raw_temp_path)
    digest = hashlib.sha256()
    tamanho = 0
    cabecalho_escrito = False
    first_url = grupo[0].parametro.url()

    def _escrever_linha(stream, valor: Any) -> None:
        nonlocal tamanho
        encoded = (json.dumps(valor, ensure_ascii=False) + "\n").encode("utf-8")
        stream.write(encoded)
        digest.update(encoded)
        tamanho += len(encoded)

    limiter = _RateLimiter(politeness_delay)

    def _fetch(chunk: DownloadChunk) -> list:
        # O delay é aplicado aqui, dentro do worker, para não bloquear a
        # thread principal — que assim consome/escreve continuamente em vez
        # de acumular respostas completas na memória durante a submissão.
        url = chunk.parametro.url()
        limiter.wait()
        return _validar_linhas(url, client.get(url))

    try:
        with os.fdopen(fd, "wb") as stream:
            executor = ThreadPoolExecutor(max_workers=max_workers)
            try:
                futures: dict[Any, DownloadChunk] = {
                    executor.submit(_fetch, chunk): chunk for chunk in grupo
                }
                for future in as_completed(futures):
                    chunk = futures[future]
                    linhas = future.result()
                    if linhas:
                        if not cabecalho_escrito:
                            _escrever_linha(stream, linhas[0])
                            cabecalho_escrito = True
                        for linha in linhas[1:]:
                            _escrever_linha(stream, linha)
                    if on_chunk_done is not None:
                        on_chunk_done(chunk)
            finally:
                executor.shutdown(wait=True)
            stream.flush()
            os.fsync(stream.fileno())
        temp_path.replace(target)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    manifest = DownloadManifest.from_digest(
        source_id="ibge",
        dataset_id=f"{agregado_id}:{nivel}",
        url=first_url,
        sha256=digest.hexdigest(),
        size_bytes=tamanho,
        path=str(target.absolute()),
        producer="sidra-fetcher",
        metadata={"nivel_territorial": nivel, "n_requests": len(grupo)},
    )
    manifest_path = target.with_suffix(target.suffix + ".manifest.json")
    manifest.write_json(manifest_path)
    return target


def download_agregado_dados(
    client: SidraClient,
    agregado_id: int,
    output_dir: str | Path,
    *,
    agregado: Agregado | None = None,
    niveis_territoriais: list[str] | None = None,
    variaveis: list[str] | None = None,
    periodos: list[str] | None = None,
    classificacoes: dict[str, list[str]] | None = None,
    limit: int = SIDRA_API_VALUES_LIMIT,
    max_workers: int = 4,
    politeness_delay: float = 0.0,
    on_chunk_done: Callable[[DownloadChunk], None] | None = None,
) -> list[Path]:
    """Baixa todos os dados de um agregado e grava um NDJSON + manifest por
    nível territorial.

    Cada linha do arquivo NDJSON é um registro do SIDRA (a primeira linha é o
    cabeçalho com os nomes amigáveis das colunas, mantido uma única vez mesmo
    quando o download exige múltiplos requests). Grava atomicamente e produz
    um ``DownloadManifest`` (SHA-256, tamanho, URL de origem) ao lado de cada
    arquivo de dados, seguindo a mesma convenção de
    :func:`sidra_fetcher.reader.save_agregado`.

    Args:
        client: Cliente já autenticado/configurado para fazer os requests.
        agregado_id: ID do agregado a baixar.
        output_dir: Diretório onde os arquivos ``dados_{nivel}.ndjson`` serão
            gravados (criado se não existir).
        agregado: Metadados já carregados, para evitar um round-trip extra
            quando o chamador já os possui.
        max_workers: Concorrência máxima de requests por nível territorial.
        politeness_delay: Pausa (segundos) entre o disparo de cada request.
        on_chunk_done: Callback opcional, chamado após cada chunk concluído
            (útil para barras de progresso).

    Returns:
        Caminhos dos arquivos de dados gravados (não dos manifests), um por
        nível territorial efetivamente baixado.
    """
    if agregado is None:
        agregado = client.get_agregado(agregado_id)

    chunks = plan_agregado_download(
        agregado,
        niveis_territoriais=niveis_territoriais,
        variaveis=variaveis,
        periodos=periodos,
        classificacoes=classificacoes,
        limit=limit,
    )

    grupos: dict[str, list[DownloadChunk]] = {}
    for chunk in chunks:
        grupos.setdefault(chunk.nivel_territorial, []).append(chunk)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for nivel, grupo in grupos.items():
        target = output_path / f"dados_{nivel}.ndjson"
        paths.append(
            _download_nivel(
                client,
                grupo,
                target,
                agregado_id=agregado_id,
                nivel=nivel,
                max_workers=max_workers,
                politeness_delay=politeness_delay,
                on_chunk_done=on_chunk_done,
            )
        )
    return paths
