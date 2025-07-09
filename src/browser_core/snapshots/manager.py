# Define o gestor de alto nível para o ciclo de vida dos snapshots.
#
# Este módulo implementa o SnapshotManager, que fornece uma API coesa
# e de fácil utilização para orquestrar o StorageEngine. Ele abstrai
# a complexidade de resolver cadeias de dependência e de calcular
# deltas, oferecendo operações semânticas como 'criar' e 'materializar'.

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..exceptions import SnapshotError, StorageEngineError
from ..storage.engine import StorageEngine
from ..types import FilePath, SnapshotData, SnapshotId
from ..utils import safe_json_dumps


class SnapshotManager:
    """
    Fornece uma API de alto nível para gerir o ciclo de vida dos snapshots.
    """

    def __init__(self, snapshots_metadata_dir: FilePath, storage_engine: StorageEngine):
        """
        Inicializa o gestor de snapshots.
        """
        self.snapshots_dir = Path(snapshots_metadata_dir)
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
                return json.loads(f.read())
        except (IOError, json.JSONDecodeError) as e:
            raise SnapshotError(
                f"Falha ao ler ou decodificar o arquivo de metadados do snapshot: {snapshot_id}",
                original_error=e
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

    def materialize_for_worker(self, snapshot_id: SnapshotId, target_dir: Path) -> SnapshotData:
        """
        Resolve a cadeia de um snapshot e instrui o StorageEngine a materializar o ambiente.
        """
        try:
            chain = self._resolve_snapshot_chain(snapshot_id)
            deltas = [s.get("delta", {}) for s in chain if s.get("delta")]

            self.storage_engine.materialize(deltas, target_dir)

            return chain[-1]
        except (SnapshotError, StorageEngineError) as e:
            raise SnapshotError(
                f"Falha ao materializar o ambiente para o snapshot '{snapshot_id}'",
                original_error=e
            )

    def create_snapshot(
            self,
            new_id: SnapshotId,
            parent_id: SnapshotId,
            final_profile_dir: Path,
            metadata: Optional[Dict[str, Any]] = None
    ) -> SnapshotData:
        """
        Cria um novo snapshot calculando o delta a partir de um perfil modificado.

        Nota: Esta é uma API de baixo nível. Para a maioria dos casos de uso,
        é recomendado utilizar o método `WorkforceManager.create_snapshot_from_task`,
        que automatiza a execução de um worker para gerar o estado final desejado.

        Args:
            new_id: O ID para o novo snapshot a ser criado.
            parent_id: O ID do snapshot que serviu de base.
            final_profile_dir: O caminho para o diretório de perfil com o estado final.
            metadata: Um dicionário opcional com dados arbitrários (ex: descrição).

        Returns:
            Os metadados do novo snapshot criado.
        """
        parent_snapshot = self.get_snapshot_data(parent_id)
        if not parent_snapshot:
            raise SnapshotError(f"Snapshot pai '{parent_id}' não encontrado.")

        with tempfile.TemporaryDirectory(prefix="browser-core-base-") as temp_base_dir:
            base_dir_path = Path(temp_base_dir)
            self.materialize_for_worker(parent_id, base_dir_path)
            delta = self.storage_engine.calculate_delta(base_dir_path, final_profile_dir)

        new_snapshot_data: SnapshotData = {
            "id": new_id,
            "parent_id": parent_id,
            "base_driver": parent_snapshot["base_driver"],
            "created_at": datetime.utcnow().isoformat() + "Z",
            "delta": delta,
            "metadata": metadata or {},
        }

        snapshot_file = self.snapshots_dir / f"{new_id}.json"
        try:
            with open(snapshot_file, "w", encoding="utf-8") as f:
                f.write(safe_json_dumps(new_snapshot_data, indent=2))
        except IOError as e:
            raise SnapshotError(
                f"Falha ao salvar o arquivo de metadados do novo snapshot: {snapshot_file}",
                original_error=e
            )

        return new_snapshot_data
