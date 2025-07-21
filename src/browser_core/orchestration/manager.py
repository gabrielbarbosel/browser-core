"""Gestor principal de orquestração para múltiplos workers."""

import logging
import queue
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

from .factory import WorkerFactory
from .worker import Worker
from ..exceptions import SnapshotError, WorkerError
from ..logging import StructuredFormatter
from ..settings import Settings, default_settings
from ..snapshots.manager import SnapshotManager
from ..storage.engine import StorageEngine
from ..types import TaskStatus, DriverInfo, LoggerProtocol
from ..drivers.manager import DriverManager
from ..drivers.manager import DriverError


class Orchestrator:
    """
    Orquestra a execução de tarefas em um ou mais workers, gerindo
    o ciclo de vida e o logging de forma centralizada e hierárquica.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Inicializa o orquestrador principal."""
        self.settings = settings or default_settings()
        paths = self.settings.get("paths", {})

        objects_dir = Path(paths.get("objects_dir"))
        snapshots_dir = Path(paths.get("snapshots_metadata_dir"))
        self.tasks_logs_dir = Path(paths.get("tasks_logs_dir"))

        storage = StorageEngine(objects_dir)
        self.snapshot_manager = SnapshotManager(snapshots_dir, storage)

        self.main_logger: logging.Logger = logging.getLogger("browser_core.workforce")
        if not self.main_logger.hasHandlers():
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            self.main_logger.addHandler(handler)
            self.main_logger.setLevel(
                self.settings.get("logging", {}).get("level", "INFO").upper()
            )

    def _ensure_driver_is_ready(self, driver_info: DriverInfo) -> None:
        """Baixa o driver necessário de forma idempotente."""
        manager = DriverManager(logger=cast(LoggerProtocol, self.main_logger), settings=self.settings)
        try:
            manager.prewarm_driver(driver_info)
        except DriverError as e:
            self.main_logger.error(str(e))
            raise

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
        self.main_logger.info(
            f"Iniciando a criação do snapshot '{new_snapshot_id}' a partir de '{base_snapshot_id}'."
        )

        base_snapshot_data = self.snapshot_manager.get_snapshot_data(base_snapshot_id)
        if not base_snapshot_data:
            raise SnapshotError(
                f"Snapshot base '{base_snapshot_id}' não encontrado. Impossível continuar."
            )

        driver_info = base_snapshot_data["base_driver"]
        workforce_run_dir = self.get_new_workforce_run_dir()

        factory = WorkerFactory(self.settings, workforce_run_dir)

        with tempfile.TemporaryDirectory(
                prefix=f"snapshot_creator_{new_snapshot_id}_"
        ) as temp_profile_dir_str:
            temp_profile_dir = Path(temp_profile_dir_str)
            self.main_logger.debug(
                f"Perfil temporário será criado em: {temp_profile_dir}"
            )

            self.snapshot_manager.materialize_for_worker(
                base_snapshot_id, temp_profile_dir
            )

            worker_instance = factory.create_worker(
                driver_info=driver_info,
                profile_dir=temp_profile_dir,
                worker_id="snapshot_creator",
            )

            try:
                with worker_instance:
                    self.main_logger.info(
                        "Executando a função de setup para modificar o estado do navegador..."
                    )
                    setup_function(worker_instance)
                    self.main_logger.info("Função de setup concluída com sucesso.")
            except Exception as e:
                self.main_logger.error(
                    f"A função de setup falhou durante a criação do snapshot: {e}",
                    exc_info=True,
                )
                raise WorkerError(
                    "A função de setup do snapshot falhou.", original_error=e
                )

            self.main_logger.info(
                f"Calculando o delta e criando os metadados para o snapshot '{new_snapshot_id}'..."
            )
            self.snapshot_manager.create_snapshot(
                new_id=new_snapshot_id,
                parent_id=base_snapshot_id,
                final_profile_dir=temp_profile_dir,
                metadata=metadata,
            )
            self.main_logger.info(f"Snapshot '{new_snapshot_id}' criado com sucesso!")

    def run_supervised_squad(
            self,
            base_snapshot_id: str,
            task_items: List[Any],
            worker_setup_function: Callable[[Worker], bool],
            item_processing_function: Callable[[Worker, Any], Any],
            squad_size: int,
            on_result_callback: Optional[Callable[[Any], None]] = None,
    ) -> List[Any]:
        """
        Executa tarefas com um esquadrão de workers de longa duração e resilientes.
        Retorna uma lista com os resultados de todas as tarefas processadas.
        """
        if not task_items:
            self.main_logger.warning("Nenhuma tarefa fornecida. Encerrando.")
            return []

        workforce_run_dir = self.get_new_workforce_run_dir()
        self.main_logger.info(
            f"Iniciando esquadrão SUPERVISIONADO de {squad_size} workers. Logs em: {workforce_run_dir}")

        task_queue = queue.Queue()
        for item in task_items:
            task_queue.put(item)

        results_list = []
        results_lock = threading.Lock()

        log_config = self.settings.get("logging", {})
        formatter = StructuredFormatter(
            format_type=log_config.get("format_type", "detailed"),
            mask_credentials=log_config.get("mask_credentials", True),
        )
        consolidated_handler = logging.FileHandler(workforce_run_dir / "consolidated.log", encoding="utf-8")
        consolidated_handler.setFormatter(formatter)

        driver_info = self.snapshot_manager.get_snapshot_data(base_snapshot_id)["base_driver"]
        self._ensure_driver_is_ready(driver_info)
        factory = WorkerFactory(self.settings, workforce_run_dir)

        def _worker_lifecycle(worker_id: int):
            worker_name = f"Worker-{worker_id}"
            self.main_logger.info(f"[{worker_name}] Iniciando ciclo de vida.")

            with tempfile.TemporaryDirectory(prefix=f"supervised_worker_{worker_id}_") as temp_profile_dir_str:
                worker_dir = Path(temp_profile_dir_str)
                self.snapshot_manager.materialize_for_worker(base_snapshot_id, worker_dir)
                worker = factory.create_worker(
                    driver_info=driver_info, profile_dir=worker_dir,
                    worker_id=f"squad_{worker_id}", consolidated_log_handler=consolidated_handler,
                )
                try:
                    with worker:
                        if not worker_setup_function(worker):
                            self.main_logger.error(f"[{worker_name}] Falha no setup inicial. Encerrando.")
                            return

                        while True:
                            try:
                                item = task_queue.get_nowait()
                            except queue.Empty:
                                self.main_logger.info(f"[{worker_name}] Fila de tarefas vazia. Encerrando.")
                                break
                            try:
                                self.main_logger.info(f"[{worker_name}] Processando item: {str(item)}")
                                result = item_processing_function(worker, item)
                                with results_lock:
                                    results_list.append(result)
                                if on_result_callback:
                                    on_result_callback(result)
                            except WorkerError as e:
                                self.main_logger.error(f"[{worker_name}] Erro crítico: {e}. Tarefa re-enfileirada.")
                                task_queue.put(item)
                                break
                            except Exception as e:
                                self.main_logger.error(f"[{worker_name}] Erro não-crítico em '{str(item)}'.",
                                                       exc_info=True)
                                error_result = self._create_error_result(item, TaskStatus.TASK_FAILED, str(e))
                                with results_lock:
                                    results_list.append(error_result)
                                if on_result_callback:
                                    on_result_callback(error_result)
                            finally:
                                task_queue.task_done()
                except Exception:
                    self.main_logger.critical(f"[{worker_name}] Falha irrecuperável no ciclo de vida.", exc_info=True)

        with ThreadPoolExecutor(max_workers=squad_size, thread_name_prefix="Supervisor") as executor:
            futures = {executor.submit(_worker_lifecycle, i): i for i in range(squad_size)}
            while futures:
                done_future = next(as_completed(futures))
                worker_id = futures.pop(done_future)
                try:
                    done_future.result()
                except Exception as e:
                    self.main_logger.critical(f"[Supervisor] Thread do Worker {worker_id} falhou: {e}", exc_info=True)
                if not task_queue.empty():
                    self.main_logger.info(f"[Supervisor] Substituindo worker {worker_id}.")
                    new_future = executor.submit(_worker_lifecycle, worker_id)
                    futures[new_future] = worker_id

        consolidated_handler.close()
        self.main_logger.info("Esquadrão supervisionado concluiu todas as tarefas.")
        return results_list

    def get_new_workforce_run_dir(self) -> Path:
        """Cria um diretório de execução único para logs e artefatos."""
        run_id = f"workforce_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        run_dir = self.tasks_logs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    @staticmethod
    def _create_error_result(
            item: Any, status: TaskStatus, reason: str
    ) -> Dict[str, Any]:
        """Cria um dicionário de resultado de erro padronizado."""
        return {"item": item, "status": status.value, "motivo": reason}

    def run_tasks_in_squad(
            self,
            base_snapshot_id: str,
            task_items: List[Any],
            worker_setup_function: Callable[[Worker], bool],
            item_processing_function: Callable[[Worker, Any], Any],
            squad_size: Optional[int] = None,
    ) -> List[Any]:
        # ... (código original deste método, sem alterações)
        if not task_items:
            self.main_logger.warning(
                "Nenhum item de tarefa fornecido. Encerrando a execução do esquadrão."
            )
            return []

        workforce_run_dir = self.get_new_workforce_run_dir()
        self.main_logger.info(
            f"Iniciando esquadrão (modo Lote). Logs e artefatos em: {workforce_run_dir}"
        )

        log_config = self.settings.get("logging", {})
        formatter = StructuredFormatter(
            format_type=log_config.get("format_type", "detailed"),
            mask_credentials=log_config.get("mask_credentials", True),
        )
        consolidated_log_path = workforce_run_dir / "consolidated.log"
        consolidated_handler = logging.FileHandler(
            consolidated_log_path, encoding="utf-8"
        )
        consolidated_handler.setFormatter(formatter)

        driver_info = self.snapshot_manager.get_snapshot_data(base_snapshot_id)["base_driver"]
        self._ensure_driver_is_ready(driver_info)
        task_queue: "queue.Queue[Any]" = queue.Queue()
        for item in task_items:
            task_queue.put(item)

        worker_instances: List[Worker] = []
        worker_dirs: List[Path] = []

        factory = WorkerFactory(self.settings, workforce_run_dir)

        def prepare_worker(i: int) -> Tuple[Path, Worker]:
            worker_dir = Path(tempfile.mkdtemp(prefix=f"squad_worker_profile_{i}_"))
            self.snapshot_manager.materialize_for_worker(base_snapshot_id, worker_dir)
            wk = factory.create_worker(
                driver_info=driver_info,
                profile_dir=worker_dir,
                worker_id=f"worker_{i}",
                consolidated_log_handler=consolidated_handler,
            )
            return worker_dir, wk

        with ThreadPoolExecutor(max_workers=squad_size) as executor:
            futures = [executor.submit(prepare_worker, i) for i in range(squad_size)]
            for future in as_completed(futures):
                d, w = future.result()
                worker_dirs.append(d)
                worker_instances.append(w)

        def squad_worker_task(worker_inst: Worker, worker_id_num: int):
            with worker_inst:
                if not worker_setup_function(worker_inst):
                    worker_inst.logger.error(
                        "Falha no setup do worker. Abortando tarefas para este worker."
                    )
                    failed = []
                    while not task_queue.empty():
                        try:
                            queued_item = task_queue.get_nowait()
                        except queue.Empty:
                            break
                        failed.append(
                            self._create_error_result(
                                queued_item, TaskStatus.SETUP_FAILED, "Falha no setup do worker"
                            )
                        )
                    return failed

                results = []
                while True:
                    try:
                        queued_item = task_queue.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        result_data = item_processing_function(worker_inst, queued_item)
                        if (
                                isinstance(result_data, dict)
                                and "status" not in result_data
                        ):
                            result_data["status"] = TaskStatus.SUCCESS.value
                        elif not isinstance(result_data, dict):
                            result_data = {
                                "item": queued_item,
                                "status": TaskStatus.SUCCESS.value,
                                "data": result_data,
                            }
                        results.append(result_data)
                    except Exception as exc:
                        worker_inst.logger.error(
                            f"Erro ao processar item '{queued_item}': {exc}", exc_info=True
                        )
                        worker_inst.capture_debug_artifacts(
                            f"erro_processamento_item_{worker_id_num}"
                        )
                        results.append(
                            self._create_error_result(
                                queued_item, TaskStatus.TASK_FAILED, str(exc)
                            )
                        )
                return results

        all_results = []
        try:
            with ThreadPoolExecutor(max_workers=squad_size) as executor:
                futures = {
                    executor.submit(squad_worker_task, worker_instances[i], i): i
                    for i in range(len(worker_instances))
                }
                for future in as_completed(futures):
                    try:
                        all_results.extend(future.result())
                    except Exception as e:
                        worker_id = futures[future]
                        self.main_logger.critical(
                            f"Erro crítico irrecuperável no worker {worker_id}: {e}",
                            exc_info=True,
                        )
            return all_results
        finally:
            self.main_logger.info(
                "Limpando diretórios de perfil temporários dos workers..."
            )
            for d in worker_dirs:
                shutil.rmtree(d, ignore_errors=True)
            consolidated_handler.close()
