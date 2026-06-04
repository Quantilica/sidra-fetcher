from pathlib import Path

from quantilica.core.storage import LocalStorage


class DataRepository:
    """Manages storage for IBGE/SIDRA metadata files using LocalStorage."""

    def __init__(self, root: Path | str):
        self.storage = LocalStorage(root)

    def path_agregado(self, agregado_id: int | str) -> Path:
        """Return the path for a specific aggregate's JSON metadata."""
        return self.storage.path_for(f"agregados/agregado_{agregado_id}.json")

    def path_indice(self) -> Path:
        """Return the path for the surveys index JSON."""
        return self.storage.path_for("agregados/indice_pesquisas.json")
