"""Sample device and host pressure during an evaluated question."""

from threading import Event, Thread

import psutil

from huggingface_agents_langgraph.model_server import gpu_memory


def host_memory() -> dict[str, int]:
    """Report host memory in MiB without allocating model buffers."""
    memory = psutil.virtual_memory()
    return {
        "available_mib": memory.available // (1024 * 1024),
        "total_mib": memory.total // (1024 * 1024),
    }


class ResourceMonitor:
    """Observe peaks without loading a model or retaining an unbounded timeline."""

    def __init__(self) -> None:
        self._stop = Event()
        self._thread = Thread(target=self._sample, daemon=True)
        self.metrics: dict = {
            "samples": 0,
            "gpu_peak_used_mib": 0,
            "minimum_available_ram_mib": None,
        }

    def start(self) -> None:
        self._thread.start()

    def finish(self) -> dict:
        self._stop.set()
        self._thread.join(timeout=4)
        return dict(self.metrics)

    def _sample(self) -> None:
        while not self._stop.is_set():
            gpu = gpu_memory()
            available = host_memory()["available_mib"]
            self.metrics["samples"] += 1
            self.metrics["gpu_peak_used_mib"] = max(
                self.metrics["gpu_peak_used_mib"],
                gpu.get("used_mib", 0),
            )
            previous = self.metrics["minimum_available_ram_mib"]
            self.metrics["minimum_available_ram_mib"] = (
                available if previous is None else min(previous, available)
            )
            self._stop.wait(1)
