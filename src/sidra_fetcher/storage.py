from pathlib import Path

from quantilica.core.storage import LocalStorage


class DataRepository:
    """Manages storage for IBGE/SIDRA metadata files using LocalStorage.

    Args:
        root (Path | str): The root directory for the storage repository.
    """

    def __init__(self, root: Path | str):
        self.storage = LocalStorage(root)

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
