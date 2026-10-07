# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Verificação de frescor (check) para agregados do SIDRA, sem download.

Compara, por nível territorial, a data máxima de modificação dos períodos
coberto pelo plano contra o mtime do NDJSON local (``dados_{nivel}.ndjson``).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

__all__ = ["check_agregado"]


def _max_modificacao(iso_dates: list[dt.date]) -> dt.date | None:
    """Maior data de modificação, ou None se vazia."""
    return max(iso_dates) if iso_dates else None


def check_agregado(
    client: Any,
    agregado_id: int,
    output_dir: str | Path,
    filtros: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Verificar frescor de um agregado sem baixar dados.

    Só toca a rede para metadados (agregado + plano); nunca baixa valores.

    Args:
        client: Cliente com ``get_agregado`` e ``plan_dados_agregado``.
        agregado_id: ID do agregado.
        output_dir: Diretório onde vivem os ``dados_{nivel}.ndjson``.
        filtros: Mesmos filtros de ``plan_dados_agregado``
            (``niveis_territoriais``, ``variaveis``, ``periodos``,
            ``classificacoes``).

    Returns:
        Tupla ``(veredictos, resumo)``: lista de veredictos no schema de
        ``CheckPlanItem`` do SDK (com ``entry`` reconstruível) e resumo com
        ``agregado_id``, ``agregado_nome`` e ``n_niveis``.
    """
    filtros = dict(filtros or {})
    agregado = client.get_agregado(agregado_id)
    chunks = client.plan_dados_agregado(agregado_id, agregado=agregado, **filtros)
    output = Path(output_dir)

    mod_por_periodo = {p.id: p.modificacao for p in agregado.periodos}
    pool_periodos = [p.id for p in agregado.periodos]

    por_nivel: dict[str, set[str]] = {}
    for chunk in chunks:
        cobertos = chunk.parametro.periodos or pool_periodos
        por_nivel.setdefault(chunk.nivel_territorial, set()).update(cobertos)

    veredictos: list[dict[str, Any]] = []
    for nivel in sorted(por_nivel):
        filename = f"dados_{nivel}.ndjson"
        target = output / filename
        mods = [
            mod_por_periodo[pid] for pid in por_nivel[nivel] if pid in mod_por_periodo
        ]
        max_mod = _max_modificacao(mods)
        existe = target.exists()
        if existe and max_mod is not None:
            limite = (
                dt.datetime(max_mod.year, max_mod.month, max_mod.day).timestamp() - 1
            )
            fresco = target.stat().st_mtime >= limite
        else:
            fresco = False
        if fresco:
            acao, motivo = "skip-up-to-date", "local-fresh"
        else:
            acao = "download"
            motivo = "not-present" if not existe else "remote-newer"
        veredictos.append(
            {
                "dataset": f"sidra-{agregado_id}",
                "id": filename,
                "url": agregado.url,
                "partition": nivel,
                "local_path": str(target),
                "remote_etag": None,
                "remote_last_modified": max_mod.isoformat() if max_mod else None,
                "remote_size": None,
                "local_exists": existe,
                "action": acao,
                "reason": motivo,
                "entry": {
                    "id": filename,
                    "url": agregado.url,
                    "dataset": f"sidra-{agregado_id}",
                    "agregado_id": agregado_id,
                    "nivel": nivel,
                    "filename": filename,
                    "filtros": filtros,
                },
            }
        )
    resumo = {
        "agregado_id": agregado_id,
        "agregado_nome": agregado.nome,
        "n_niveis": len(por_nivel),
    }
    return veredictos, resumo
