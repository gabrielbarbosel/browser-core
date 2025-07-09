# browser-core/src/browser_core/workforce.py
# ...
import logging
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from .exceptions import SnapshotError, WorkerError
from .logging import StructuredFormatter  # A importação de setup_task_logger não é mais necessária aqui
from .settings import Settings, default_settings
from .snapshots.manager import SnapshotManager
from .storage.engine import StorageEngine
from .types import TaskStatus
from .worker import Worker
from .worker_factory import WorkerFactory  # Importa a nova factory


class WorkforceManager:
    """
    Orquestra a execução de tarefas em um ou mais workers, gerindo
    o ciclo de vida e o logging de forma centralizada e hierárquica.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Inicializa o WorkforceManager.
        """
        self.settings = settings or default_settings()
        paths = self.settings.get("paths", {})

        objects_dir = Path(paths.get("objects_dir"))
        snapshots_dir = Path(paths.get("snapshots_metadata_dir"))
        self.tasks_logs_dir = Path(paths.get("tasks_logs_dir"))

        storage = StorageEngine(objects_dir)
        self.snapshot_manager = SnapshotManager(snapshots_dir, storage)

        self.main_logger = logging.getLogger("browser_core.workforce")
        if not self.main_logger.hasHandlers():
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.main_logger.addHandler(handler)
        self.main_logger.setLevel(self.settings.get("logging", {}).get("level", "INFO").upper())

    def create_snapshot_from_task(
            self,
            base_snapshot_id: str,
            new_snapshot_id: str,
            setup_function: Callable[[Worker], None],
            metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Cria um novo snapshot executando uma tarefa de setup a partir de um estado base.
        """
        self.main_logger.info(f"Iniciando a criação do snapshot '{new_snapshot_id}' a partir de '{base_snapshot_id}'.")

        base_snapshot_data = self.snapshot_manager.get_snapshot_data(base_snapshot_id)
        if not base_snapshot_data:
            raise SnapshotError(f"Snapshot base '{base_snapshot_id}' não encontrado. Impossível continuar.")

        driver_info = base_snapshot_data["base_driver"]
        workforce_run_dir = self._get_new_workforce_run_dir()

        # A factory gerencia a criação do worker
        factory = WorkerFactory(self.settings, workforce_run_dir)

        with tempfile.TemporaryDirectory(prefix=f"snapshot_creator_{new_snapshot_id}_") as temp_profile_dir_str:
            temp_profile_dir = Path(temp_profile_dir_str)
            self.main_logger.debug(f"Perfil temporário será criado em: {temp_profile_dir}")

            self.snapshot_manager.materialize_for_worker(base_snapshot_id, temp_profile_dir)

            worker = factory.create_worker(
                driver_info=driver_info,
                profile_dir=temp_profile_dir,
                worker_id="snapshot_creator"
            )

            try:
                with worker:
                    self.main_logger.info("Executando a função de setup para modificar o estado do navegador...")
                    setup_function(worker)
                    self.main_logger.info("Função de setup concluída com sucesso.")
            except Exception as e:
                self.main_logger.error(f"A função de setup falhou durante a criação do snapshot: {e}", exc_info=True)
                raise WorkerError("A função de setup do snapshot falhou.", original_error=e)

            self.main_logger.info(f"Calculando o delta e criando os metadados para o snapshot '{new_snapshot_id}'...")
            self.snapshot_manager.create_snapshot(
                new_id=new_snapshot_id,
                parent_id=base_snapshot_id,
                final_profile_dir=temp_profile_dir,
                metadata=metadata
            )
            self.main_logger.info(f"Snapshot '{new_snapshot_id}' criado com sucesso!")

    def run_tasks_in_squad(
            self,
            squad_size: int,
            base_snapshot_id: str,
            task_items: List[Any],
            worker_setup_function: Callable[[Worker], bool],
            item_processing_function: Callable[[Worker, Any], Any],
    ) -> List[Any]:
        """
        Executa tarefas num "esquadrão" de workers persistentes.
        """
        if not task_items:
            self.main_logger.warning("Nenhum item de tarefa fornecido. Encerrando a execução do esquadrão.")
            return []

        workforce_run_dir = self._get_new_workforce_run_dir()
        self.main_logger.info(f"Iniciando esquadrão. Logs e artefatos em: {workforce_run_dir}")

        log_config = self.settings.get("logging", {})
        formatter = StructuredFormatter(
            format_type=log_config.get("format_type", "detailed"),
            mask_credentials=log_config.get("mask_credentials", True),
        )
        consolidated_log_path = workforce_run_dir / "consolidated.log"
        consolidated_handler = logging.FileHandler(consolidated_log_path, encoding='utf-8')
        consolidated_handler.setFormatter(formatter)

        driver_info = self.snapshot_manager.get_snapshot_data(base_snapshot_id)["base_driver"]
        task_chunks = np.array_split(task_items, squad_size)
        worker_instances = []
        worker_dirs = []

        # A factory gerencia a criação dos workers do esquadrão
        factory = WorkerFactory(self.settings, workforce_run_dir)

        for i in range(squad_size):
            worker_dir = Path(tempfile.mkdtemp(prefix=f"squad_worker_profile_{i}_"))
            worker_dirs.append(worker_dir)
            self.snapshot_manager.materialize_for_worker(base_snapshot_id, worker_dir)

            worker = factory.create_worker(
                driver_info=driver_info,
                profile_dir=worker_dir,
                worker_id=f"worker_{i}",
                consolidated_log_handler=consolidated_handler
            )
            worker_instances.append(worker)

        def squad_worker_task(worker: Worker, chunk: List[Any], worker_id: int):
            with worker:
                if not worker_setup_function(worker):
                    worker.logger.error("Falha no setup do worker. Abortando tarefas para este worker.")
                    return [self._create_error_result(item, TaskStatus.SETUP_FAILED, "Falha no setup do worker") for
                            item in chunk]

                results = []
                for item in chunk:
                    try:
                        result_data = item_processing_function(worker, item)
                        if isinstance(result_data, dict) and "status" not in result_data:
                            result_data["status"] = TaskStatus.SUCCESS.value
                        results.append(result_data)
                    except Exception as e:
                        worker.logger.error(f"Erro ao processar item '{item}': {e}", exc_info=True)
                        worker.capture_debug_artifacts(f"erro_processamento_item_{worker_id}")
                        results.append(self._create_error_result(item, TaskStatus.TASK_FAILED, str(e)))
                return results

        all_results = []
        try:
            with ThreadPoolExecutor(max_workers=squad_size) as executor:
                futures = {
                    executor.submit(squad_worker_task, worker_instances[i], task_chunks[i].tolist(), i): i
                    for i, chunk in enumerate(task_chunks) if chunk.size > 0
                }
                for future in as_completed(futures):
                    try:
                        all_results.extend(future.result())
                    except Exception as e:
                        worker_id = futures[future]
                        self.main_logger.critical(f"Erro crítico irrecuperável no worker {worker_id}: {e}",
                                                  exc_info=True)
        finally:
            self.main_logger.info("Limpando diretórios de perfil temporários dos workers...")
            for d in worker_dirs:
                shutil.rmtree(d, ignore_errors=True)
            consolidated_handler.close()

        return all_results

    def _get_new_workforce_run_dir(self) -> Path:
        """Cria um diretório de execução único para logs e artefatos."""
        run_id = f"workforce_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        run_dir = self.tasks_logs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def _create_error_result(self, item: Any, status: TaskStatus, reason: str) -> Dict[str, Any]:
        """Cria um dicionário de resultado de erro padronizado."""
        return {"item": item, "status": status.value, "motivo": reason}
