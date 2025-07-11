# Fornece funções utilitárias genéricas para o framework browser-core.
#
# Este módulo contém funções auxiliares e independentes usadas
# em diversas partes do sistema para tarefas comuns como validação,
# manipulação de arquivos e formatação de dados.

import json
import re
import time
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    List,
    Generator,
)

from .exceptions import ConfigurationError
from .types import FilePath

D = TypeVar("D", bound=Dict[str, Any])


# noinspection GrazieInspection
def validate_timeout(timeout: Union[int, float], min_value: int = 100) -> int:
    """
    Valida e normaliza um valor de timeout para milissegundos.

    Args:
        timeout: O valor de timeout a ser validado (em ms).
        min_value: O Valor mínimo permitido para o timeout.

    Returns:
        O timeout validado como um inteiro.
    """
    if not isinstance(timeout, (int, float)):
        raise ConfigurationError(
            f"O valor de timeout deve ser numérico, mas foi recebido {type(timeout).__name__}"
        )

    timeout_ms = int(timeout)
    if timeout_ms < min_value:
        raise ConfigurationError(
            f"O valor de timeout deve ser de no mínimo {min_value}ms, mas foi recebido {timeout_ms}ms"
        )
    return timeout_ms


def validate_selector(selector: str) -> str:
    """
    Valida e normaliza uma string de seletor.

    Garante que o seletor não seja uma string vazia ou contendo apenas espaços
    e remove espaços em branco no início e no fim.
    """
    if not isinstance(selector, str) or not selector.strip():
        raise ConfigurationError("O seletor não pode ser uma string vazia.")
    return selector.strip()


def ensure_directory(path: FilePath) -> Path:
    """Garante que um diretório exista, criando-o se necessário, de forma segura."""
    dir_path = Path(path)
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path
    except (OSError, PermissionError) as e:
        raise ConfigurationError(
            f"Não foi possível criar o diretório {dir_path}: {e}", original_error=e
        )


def deep_merge_dicts(base: D, override: Dict[str, Any]) -> D:
    """
    Mescla dois dicionários recursivamente ('deep merge').

    Valores no dicionário 'override' têm precedência. Se uma chave existe em ambos
    e os valores são dicionários, eles são mesclados recursivamente.
    O tipo do dicionário base (ex: dict, Settings) é preservado.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def retry_on_exception(
    func: Callable[..., Any],
    max_attempts: int = 3,
    delay_ms: int = 1000,
    exceptions_to_catch: Tuple[Type[Exception], ...] = (Exception,),
) -> Any:
    """Executa uma função e tenta executá-la novamente em caso de exceções específicas."""
    last_exception: Optional[Exception] = None
    current_delay_s = float(delay_ms) / 1_000.0

    for attempt in range(max_attempts):
        try:
            return func()
        except exceptions_to_catch as e:
            last_exception = e
            if attempt < max_attempts - 1:
                time.sleep(current_delay_s)
    if last_exception:
        raise last_exception
    return None


def mask_sensitive_data(data: str) -> str:
    """Mascara dados sensíveis numa string, como palavras-passe ou tokens."""
    # Padrão melhorado para capturar variações comuns de chaves de credenciais.
    patterns = [
        r"""(?i)(password|token|senha|credencial|secret|key)['"]?\s*[:=]\s*['"]?([\w.-]+)"""
    ]
    masked_data = data
    for pattern in patterns:
        masked_data = re.sub(
            pattern, lambda m: m.group(0).replace(m.group(2), "***"), masked_data
        )
    return masked_data


def safe_json_loads(data: str, default: Any = None) -> Any:
    """
    Desserializa uma string JSON de forma segura, retornando um valor padrão em caso de erro.
    """
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(data: Any, indent: Optional[int] = 2) -> str:
    """Serializa um objeto Python para uma string JSON de forma segura."""
    try:
        # Usa 'default=str' para lidar com tipos não serializáveis como Path ou datetime.
        return json.dumps(data, ensure_ascii=False, indent=indent, default=str)
    except (TypeError, ValueError):
        return "{}"


def clean_filename(filename: str, max_length: int = 255) -> str:
    """Limpa uma string para que ela possa ser usada como um nome de arquivo válido."""
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", filename)
    cleaned = re.sub(r"[\s.]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_")[:max_length] or "unnamed_file"


def _split_list(data: List[Any], n_chunks: int) -> Generator[List[Any], None, None]:
    """
    Divide uma lista em 'n' pedaços (chunks) de tamanho o mais uniforme possível.
    Esta função não depende de bibliotecas externas como o NumPy.

    Args:
        data: A lista de itens a ser dividida.
        n_chunks: O número de pedaços a serem criados.

    Yields:
        Um gerador que produz cada chunk como uma lista.
    """
    if n_chunks <= 0:
        raise ValueError("O número de chunks deve ser maior que zero.")
    # Calcula o tamanho base de cada chunk e quantos elementos "sobram"
    k, m = divmod(len(data), n_chunks)
    # Distribui os elementos que sobraram um a um para os primeiros 'm' chunks
    for i in range(n_chunks):
        start = i * k + min(i, m)
        end = (i + 1) * k + min(i + 1, m)
        yield data[start:end]
