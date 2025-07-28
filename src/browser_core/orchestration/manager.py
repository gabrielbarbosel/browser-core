"""
Define o Orchestrator, o cérebro da automação que gere a execução
de tarefas em múltiplos workers.
"""

import logging
import queue
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

from .factory import WorkerFactory
from .worker import Worker
from ..exceptions import SnapshotError, WorkerError, BrowserCrashError
from ..logging import StructuredFormatter
from ..settings import Settings, default_settings
from ..snapshots.manager import SnapshotManager
from ..storage.engine import StorageEngine
from ..types import TaskStatus, DriverInfo, LoggerProtocol, SquadConfig
from ..drivers.manager import DriverManager
from ..drivers.manager import DriverError


class Orchestrator:
    """
    Orquestra a execução de tarefas, gerindo workers, snapshots e logging.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Inicializa o orquestrador com as configurações fornecidas ou padrão."""
        self.settings = settings or default_settings()
        paths = self.settings.get("paths", {})

        objects_dir = Path(paths.get("objects_dir"))
        snapshots_dir = Path(paths.get("snapshots_metadata_dir"))
        self.tasks_logs_dir = Path(paths.get("tasks_logs_dir"))

        storage = StorageEngine(objects_dir)
        self.snapshot_manager = SnapshotManager(snapshots_dir, storage)

        self.main_logger: logging.Logger = logging.getLogger("browser_core.orchestrator")
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
        """Garante que o WebDriver necessário está descarregado antes de iniciar os workers."""
        manager = DriverManager(logger=cast(LoggerProtocol, self.main_logger), settings=self.settings)
        try:
            manager.prewarm_driver(driver_info)
        except DriverError as e:
            self.main_logger.error(str(e))
            raise

    # --- ARQUITETURA DE PLATAFORMA MULTI-ESQUADRÃO ---

    def launch_squads(
            self,
            squad_configs: List[SquadConfig],
            base_snapshot_id: str,
            worker_setup_function: Callable[[Worker], bool],
            shutdown_event: threading.Event,
            queue_names: List[str]
    ) -> Tuple[List[threading.Thread], Dict[str, queue.Queue]]:
        """
        Lança múltiplos esquadrões de workers, cria a infraestrutura de filas
        e retorna as threads e o contexto partilhado para gestão externa.
        """
        self.main_logger.info(f"A iniciar plataforma com {len(squad_configs)} esquadrão(ões).")
        threads: List[threading.Thread] = []

        # O framework cria as filas com base nos nomes fornecidos
        shared_context = {name: queue.Queue() for name in queue_names}

        try:
            driver_info = self.snapshot_manager.get_snapshot_data(base_snapshot_id)["base_driver"]
            self._ensure_driver_is_ready(driver_info)
        except (TypeError, SnapshotError) as e:
            self.main_logger.critical(
                f"Não foi possível obter informações do snapshot base '{base_snapshot_id}'. Erro: {e}")
            raise

        workforce_run_dir = self.get_new_workforce_run_dir()
        self.main_logger.info(f"Logs para esta execução em: {workforce_run_dir}")

        log_config = self.settings.get("logging", {})
        formatter = StructuredFormatter(
            format_type=log_config.get("format_type", "detailed"),
            mask_credentials=log_config.get("mask_credentials", True),
        )
        consolidated_handler = logging.FileHandler(workforce_run_dir / "consolidated.log", encoding="utf-8")
        consolidated_handler.setFormatter(formatter)

        for config in squad_configs:
            input_queue_name = config['tasks_queue']
            if input_queue_name not in shared_context:
                raise ValueError(
                    f"A fila '{input_queue_name}' definida para o esquadrão '{config['squad_name']}' não foi declarada em 'queue_names'.")

            input_queue = shared_context[input_queue_name]

            for i in range(config["num_workers"]):
                worker_name = f"{config['squad_name']}-{i + 1}"
                thread = threading.Thread(
                    target=self._worker_lifecycle,
                    args=(
                        worker_name, base_snapshot_id, driver_info,
                        worker_setup_function, config["processing_function"],
                        input_queue, shared_context, shutdown_event,
                        workforce_run_dir, consolidated_handler
                    ),
                    daemon=True
                )
                threads.append(thread)
                thread.start()

        self.main_logger.info("Todas as threads dos esquadrões foram lançadas.")
        return threads, shared_context

    def _worker_lifecycle(
            self, worker_name: str, base_snapshot_id: str, driver_info: DriverInfo,
            setup_func: Callable, processing_func: Callable,
            tasks_queue: queue.Queue, shared_context: Dict, shutdown_event: threading.Event,
            workforce_run_dir: Path, consolidated_handler: logging.Handler
    ):
        """Define o ciclo de vida de um único worker: pegar tarefa, executar e repetir."""
        squad_name = worker_name.split('-')[0]
        worker_log_dir = workforce_run_dir / squad_name
        factory = WorkerFactory(self.settings, worker_log_dir)

        self.main_logger.info(f"[{worker_name}] Ciclo de vida iniciado.")

        while not shutdown_event.is_set():
            try:
                task = tasks_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                with tempfile.TemporaryDirectory(prefix=f"worker_{worker_name}_") as temp_dir:
                    profile_dir = Path(temp_dir)
                    self.snapshot_manager.materialize_for_worker(base_snapshot_id, profile_dir)

                    worker = factory.create_worker(
                        driver_info,
                        profile_dir,
                        worker_name,
                        consolidated_log_handler=consolidated_handler
                    )

                    with worker:
                        if not setup_func(worker):
                            raise WorkerError("Falha na função de setup do worker.")

                        processing_func(worker=worker, task=task, context=shared_context)

            except (BrowserCrashError, WorkerError) as e:
                self.main_logger.error(f"[{worker_name}] Erro de worker processando '{task}': {e}. A reenfileirar.")
                tasks_queue.put(task)
            except Exception as e:
                self.main_logger.critical(f"[{worker_name}] Erro fatal processando '{task}': {e}", exc_info=True)
                if 'failed_queue' in shared_context:
                    shared_context['failed_queue'].put(task)
            finally:
                tasks_queue.task_done()

        self.main_logger.info(f"[{worker_name}] Sinal de encerramento recebido. A finalizar.")

    def create_snapshot_from_task(
            self,
            base_snapshot_id: str,
            new_snapshot_id: str,
            setup_function: Callable[[Worker], None],
            metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Cria um novo snapshot a partir de uma função de setup (ex: login)."""
        self.main_logger.info(f"Iniciando a criação do snapshot '{new_snapshot_id}' a partir de '{base_snapshot_id}'.")
        base_snapshot_data = self.snapshot_manager.get_snapshot_data(base_snapshot_id)
        if not base_snapshot_data:
            raise SnapshotError(
                f"Snapshot base '{base_snapshot_id}' não encontrado. Impossível continuar."
            )

        driver_info = base_snapshot_data["base_driver"]
        workforce_run_dir = self.get_new_workforce_run_dir()
        factory = WorkerFactory(self.settings, workforce_run_dir)

        with tempfile.TemporaryDirectory(prefix=f"snapshot_creator_{new_snapshot_id}_") as temp_profile_dir_str:
            temp_profile_dir = Path(temp_profile_dir_str)
            self.snapshot_manager.materialize_for_worker(base_snapshot_id, temp_profile_dir)
            worker_instance = factory.create_worker(
                driver_info=driver_info, profile_dir=temp_profile_dir, worker_id="snapshot_creator",
            )
            try:
                with worker_instance:
                    setup_function(worker_instance)
            except Exception as e:
                raise WorkerError("A função de setup do snapshot falhou.", original_error=e)

            self.snapshot_manager.create_snapshot(
                new_id=new_snapshot_id, parent_id=base_snapshot_id,
                final_profile_dir=temp_profile_dir, metadata=metadata,
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
        Executa uma única lista de tarefas até à sua conclusão.

        Este método mantém uma interface simples para casos de uso diretos,
        gerindo internamente a nova arquitetura de plataforma.
        """
        self.main_logger.info("A executar em modo de esquadrão supervisionado (interface legada).")

        def processing_wrapper(worker: Worker, task: Dict, context: Dict[str, queue.Queue]):
            """Adapta a função de processamento do utilizador à nova arquitetura interna."""
            try:
                task_result = item_processing_function(worker, task)
                context['results_queue'].put(task_result)
            except Exception as e:
                error_result = self._create_error_result(task, TaskStatus.TASK_FAILED, str(e))
                context['results_queue'].put(error_result)

        # Define os nomes das filas que esta função simples necessita
        queue_names = ["main_tasks_queue", "results_queue", "failed_queue"]

        squad_config: SquadConfig = {
            "squad_name": "SupervisedSquad", "num_workers": squad_size,
            "processing_function": processing_wrapper, "tasks_queue": "main_tasks_queue"
        }

        shutdown_event = threading.Event()

        worker_threads, shared_context = self.launch_squads(
            squad_configs=[squad_config], base_snapshot_id=base_snapshot_id,
            worker_setup_function=worker_setup_function, shutdown_event=shutdown_event,
            queue_names=queue_names
        )

        for item in task_items:
            shared_context["main_tasks_queue"].put(item)

        all_results = []
        try:
            shared_context["main_tasks_queue"].join()
            time.sleep(1)
        except KeyboardInterrupt:
            self.main_logger.warning("\n'Ctrl+C' recebido! A solicitar o encerramento...")
        finally:
            shutdown_event.set()
            for t in worker_threads:
                t.join()

        while not shared_context["results_queue"].empty():
            final_result = shared_context["results_queue"].get()
            if on_result_callback:
                on_result_callback(final_result)
            all_results.append(final_result)

        return all_results

    def get_new_workforce_run_dir(self, sub_dir: Optional[str] = None) -> Path:
        """Cria um diretório de execução único para logs e artefatos."""
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        run_dir = self.tasks_logs_dir / run_id
        if sub_dir:
            run_dir = run_dir / sub_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    @staticmethod
    def _create_error_result(
            task_item: Any, status: TaskStatus, reason: str
    ) -> Dict[str, Any]:
        """Cria um dicionário de resultado de erro padronizado."""
        return {"item": task_item, "status": status.value, "motivo": reason}

    def run_tasks_in_squad(
            self,
            base_snapshot_id: str,
            task_items: List[Any],
            worker_setup_function: Callable[[Worker], bool],
            item_processing_function: Callable[[Worker, Any], Any],
            squad_size: Optional[int] = None,
    ) -> List[Any]:
        """Executa tarefas em modo 'lote', onde cada worker é de curta duração."""
        if not task_items:
            self.main_logger.warning("Nenhum item de tarefa fornecido.")
            return []

        workforce_run_dir = self.get_new_workforce_run_dir()
        self.main_logger.info(f"Iniciando esquadrão (modo Lote). Logs em: {workforce_run_dir}")

        log_config = self.settings.get("logging", {})
        formatter = StructuredFormatter(
            format_type=log_config.get("format_type", "detailed"),
            mask_credentials=log_config.get("mask_credentials", True),
        )
        consolidated_handler = logging.FileHandler(workforce_run_dir / "consolidated.log", encoding="utf-8")
        consolidated_handler.setFormatter(formatter)

        driver_info = self.snapshot_manager.get_snapshot_data(base_snapshot_id)["base_driver"]
        self._ensure_driver_is_ready(driver_info)
        task_queue: "queue.Queue[Any]" = queue.Queue()
        for current_task_item in task_items:
            task_queue.put(current_task_item)

        worker_instances: List[Worker] = []
        worker_dirs: List[Path] = []
        factory = WorkerFactory(self.settings, workforce_run_dir)

        def prepare_worker(i: int) -> Tuple[Path, Worker]:
            worker_dir = Path(tempfile.mkdtemp(prefix=f"squad_worker_profile_{i}_"))
            self.snapshot_manager.materialize_for_worker(base_snapshot_id, worker_dir)
            wk = factory.create_worker(
                driver_info=driver_info, profile_dir=worker_dir,
                worker_id=f"worker_{i}", consolidated_log_handler=consolidated_handler,
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
                    worker_inst.logger.error("Falha no setup do worker.")
                    return [self._create_error_result(t, TaskStatus.SETUP_FAILED, "Falha no setup") for t in
                            list(task_queue.queue)]

                worker_results = []
                while not task_queue.empty():
                    try:
                        queued_item = task_queue.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        result_data = item_processing_function(worker_inst, queued_item)
                        worker_results.append(result_data)
                    except Exception as exc:
                        worker_inst.capture_debug_artifacts(f"erro_item_{worker_id_num}")
                        worker_results.append(self._create_error_result(queued_item, TaskStatus.TASK_FAILED, str(exc)))
                return worker_results

        all_results = []
        try:
            with ThreadPoolExecutor(max_workers=squad_size) as executor:
                futures = {executor.submit(squad_worker_task, inst, i): i for i, inst in enumerate(worker_instances)}
                for future in as_completed(futures):
                    all_results.extend(future.result())
            return all_results
        finally:
            self.main_logger.info("Limpando diretórios de perfil temporários.")
            for d in worker_dirs:
                shutil.rmtree(d, ignore_errors=True)
            consolidated_handler.close()
