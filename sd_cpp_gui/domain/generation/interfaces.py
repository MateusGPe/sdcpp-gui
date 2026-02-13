from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from sd_cpp_gui.domain.generation.engine import ExecutionResult


class IGenerator(ABC):
    """
    Abstract Interface for generation backends (CLI and Server).
    """

    @abstractmethod
    def run(
        self,
        model_path: str,
        prompt: str,
        params: List[Dict[str, Any]],
        output_path: str,
        log_file_path: Optional[str],
        on_finish: Callable[[bool, ExecutionResult], None],
    ) -> None:
        """
        Starts the generation process.

        Args:
            model_path: Path to the checkpoint.
            prompt: The positive prompt string.
            params: List of parameter dictionaries [{'flag':..., 'value':...}].
            output_path: Where to save the result.
            log_file_path: Optional path to save raw logs.
            on_finish: Callback (success, result_dict).
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stops the current generation immediately."""
        pass
