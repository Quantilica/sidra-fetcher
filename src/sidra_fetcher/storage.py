import datetime as dt
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from quantilica.core.manifests import DownloadManifest, write_manifest_sidecar
from quantilica.core.storage import BaseDataRepository


class DataRepository(BaseDataRepository):
    """Manages storage for IBGE/SIDRA metadata files using LocalStorage.

    Args:
        root (Path | str): The root directory for the storage repository.
    """

    def __init__(self, root: Path | str):
        super().__init__(root)
        self.source_id = "sidra"

    def path_for_entry(
        self,
        entry: Mapping[str, Any],
        *,
        last_modified: dt.date | dt.datetime | None = None,
        precision: Literal["date", "datetime"] = "date",
        subdir_by_year: bool = False,
    ) -> Path:
        """Return the destination path of an entry in the SIDRA layout.

        Overrides ``BaseDataRepository.path_for_entry``: the SIDRA layout is a
        fixed contract (``agregados/agregado_<id>.json`` and
        ``agregados/<id>/dados_<nivel>.ndjson``), without timestamped names or
        partition tokens, so ``last_modified``, ``precision`` and
        ``subdir_by_year`` are accepted for signature compatibility and ignored.

        Args:
            entry (Mapping[str, Any]): Entry with the aggregate ``id`` and,
                optionally, the ``nivel_territorial`` of a data file.
            last_modified (dt.date | dt.datetime | None): Ignored.
            precision (Literal["date", "datetime"]): Ignored.
            subdir_by_year (bool): Ignored.

        Returns:
            Path: The aggregate metadata path, or the data path when the entry
                carries a ``nivel_territorial``.
        """
        agregado_id = entry["id"]
        nivel = entry.get("nivel_territorial")
        if nivel:
            return self.path_dados(agregado_id, str(nivel))
        return self.path_agregado(agregado_id)

    def path_agregado(self, agregado_id: int | str) -> Path:
        """Return the path for a specific aggregate's JSON metadata.

        Args:
            agregado_id (int | str): The ID of the aggregate.

        Returns:
            Path: The path to the aggregate's JSON metadata file.
        """
        return self.storage.path_for(f"agregados/agregado_{agregado_id}.json")

    def path_indice(self) -> Path:
        """Return the path for the surveys index JSON.

        Returns:
            Path: The path to the surveys index JSON file.
        """
        return self.storage.path_for("agregados/indice_pesquisas.json")

    def path_dados(self, agregado_id: int | str, nivel_territorial: str) -> Path:
        """Return the path for one territorial level's downloaded data (NDJSON).

        Args:
            agregado_id (int | str): The ID of the aggregate.
            nivel_territorial (str): The territorial level code (e.g., 'N1', 'N3').

        Returns:
            Path: The path to the downloaded NDJSON data file.
        """
        return self.storage.path_for(
            f"agregados/{agregado_id}/dados_{nivel_territorial}.ndjson"
        )

    def write_manifest_for(
        self,
        path: Path,
        *,
        dataset_id: str,
        url: str,
        content: bytes | None = None,
        sha256: str | None = None,
        size_bytes: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Path:
        """Gera e grava o manifesto sidecar para um arquivo do repositório."""
        if content is not None:
            manifest = DownloadManifest.from_content(
                source_id=self.source_id,
                dataset_id=dataset_id,
                url=url,
                content=content,
                path=str(path.absolute()),
                producer="sidra-fetcher",
                metadata=metadata,
            )
        elif sha256 is not None and size_bytes is not None:
            manifest = DownloadManifest.from_digest(
                source_id=self.source_id,
                dataset_id=dataset_id,
                url=url,
                sha256=sha256,
                size_bytes=size_bytes,
                path=str(path.absolute()),
                producer="sidra-fetcher",
                metadata=metadata,
            )
        else:
            raise ValueError("Informe 'content' ou ('sha256' e 'size_bytes')")
        return write_manifest_sidecar(path, manifest)
