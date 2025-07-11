# Define o gestor de alto nível para o ciclo de vida dos snapshots.
#
# Este módulo implementa o SnapshotManager, que fornece uma API coesa
# e de fácil utilização para orquestrar o StorageEngine. Ele abstrai
# a complexidade de resolver cadeias de dependência e de calcular
# deltas, oferecendo operações semânticas como 'criar' e 'materializar'.

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..exceptions import SnapshotError, StorageEngineError
from ..storage.engine import StorageEngine
from ..types import FilePath, SnapshotData, SnapshotId, DriverInfo
from ..utils import safe_json_dumps


class SnapshotManager:
    """
    Fornece uma API de alto nível para gerenciar o ciclo de vida dos snapshots.
    """

    def __init__(self, snapshots_metadata_dir: FilePath, storage_engine: StorageEngine):
        """
        Inicializa o gestor de snapshots.
        """
        self.snapshots_dir = Path(snapshots_metadata_dir)
        self.snapshots_dir.mkdir(
            parents=True, exist_ok=True
        )  # Garante que o diretório exista
        self.storage_engine = storage_engine

    def get_snapshot_data(self, snapshot_id: SnapshotId) -> Optional[SnapshotData]:
        """
        Carrega os metadados de um snapshot a partir do seu ID.
        """
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
        if not snapshot_file.exists():
            return None
        try:
            with open(snapshot_file, "r", encoding="utf-8") as f:
                # A asserção de tipo aqui garante ao mypy que o retorno é compatível com SnapshotData
                return json.loads(f.read())
        except (IOError, json.JSONDecodeError) as e:
            raise SnapshotError(
                f"Falha ao ler ou decodificar o arquivo de metadados do snapshot: {snapshot_id}",
                original_error=e,
            )

    def _resolve_snapshot_chain(self, snapshot_id: SnapshotId) -> List[SnapshotData]:
        """
        Resolve a cadeia de dependências de um snapshot, do mais antigo ao atual.
        """
        chain: List[SnapshotData] = []
        current_id: Optional[SnapshotId] = snapshot_id

        while current_id:
            data = self.get_snapshot_data(current_id)
            if not data:
                raise SnapshotError(
                    f"Snapshot '{current_id}' não encontrado durante a resolução da cadeia para '{snapshot_id}'."
                )
            chain.append(data)
            current_id = data.get("parent_id")

        return list(reversed(chain))

    def materialize_for_worker(
        self, snapshot_id: SnapshotId, target_dir: Path
    ) -> SnapshotData:
        """
        Resolve a cadeia de um snapshot e instrui o StorageEngine a materializar o ambiente.
        """
        try:
            chain = self._resolve_snapshot_chain(snapshot_id)

            # Coleta os deltas de cada snapshot na cadeia.
            # A verificação 'if s.get("delta")' garante que apenas snapshots com
            # alterações (deltas não vazios) sejam incluídos na materialização.
            deltas = [s.get("delta", {}) for s in chain if s.get("delta")]

            self.storage_engine.materialize(deltas, target_dir)

            return chain[-1]
        except (SnapshotError, StorageEngineError) as e:
            raise SnapshotError(
                f"Falha ao materializar o ambiente para o snapshot '{snapshot_id}'",
                original_error=e,
            )

    def create_base_snapshot(
        self,
        new_id: SnapshotId,
        driver_info: DriverInfo,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SnapshotData:
        """
        Cria um snapshot "raiz" (base), sem pai e com um perfil vazio.
        """
        if self.get_snapshot_data(new_id):
            raise SnapshotError(f"Já existe um snapshot com o ID '{new_id}'.")

        new_snapshot_data: SnapshotData = {
            "id": new_id,
            "parent_id": None,
            "base_driver": driver_info,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "delta": {},
            "metadata": metadata if metadata is not None else {},
        }

        self._save_snapshot_data(new_id, new_snapshot_data)
        return new_snapshot_data

    def create_snapshot(
        self,
        new_id: SnapshotId,
        parent_id: SnapshotId,
        final_profile_dir: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SnapshotData:
        """
        Cria um novo snapshot calculando o delta a partir de um perfil modificado.
        """
        if self.get_snapshot_data(new_id):
            raise SnapshotError(f"Já existe um snapshot com o ID '{new_id}'.")

        parent_snapshot = self.get_snapshot_data(parent_id)
        if not parent_snapshot:
            raise SnapshotError(f"Snapshot pai '{parent_id}' não encontrado.")

        with tempfile.TemporaryDirectory(prefix="browser-core-base-") as temp_base_dir:
            base_dir_path = Path(temp_base_dir)
            self.materialize_for_worker(parent_id, base_dir_path)
            delta = self.storage_engine.calculate_delta(
                base_dir_path, final_profile_dir
            )

        new_snapshot_data: SnapshotData = {
            "id": new_id,
            "parent_id": parent_id,
            "base_driver": parent_snapshot["base_driver"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "delta": delta,
            "metadata": metadata if metadata is not None else {},
        }

        self._save_snapshot_data(new_id, new_snapshot_data)
        return new_snapshot_data

    def _save_snapshot_data(self, snapshot_id: SnapshotId, data: SnapshotData) -> None:
        """Método auxiliar para salvar os metadados de um snapshot."""
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
        try:
            with open(snapshot_file, "w", encoding="utf-8") as f:
                f.write(safe_json_dumps(data, indent=2))
        except IOError as e:
            raise SnapshotError(
                f"Falha ao salvar o arquivo de metadados do novo snapshot: {snapshot_file}",
                original_error=e,
            )
