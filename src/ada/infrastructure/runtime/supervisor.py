"""Small multiprocessing supervisor for API, inference and autonomy workers."""

import multiprocessing
from functools import partial


class ServiceSupervisor:
    def __init__(self, targets):
        self.targets = dict(targets)
        self.processes = {}
        self.stopping = False

    def start(self):
        for name, target in self.targets.items():
            process = multiprocessing.Process(target=target, name=f"ada-{name}", daemon=False)
            process.start()
            self.processes[name] = process
        return self.processes

    def stop(self):
        self.stopping = True
        for process in self.processes.values():
            if process.is_alive():
                process.terminate()
        for process in self.processes.values():
            process.join(timeout=5)

    def wait(self):
        try:
            for process in self.processes.values():
                process.join()
        except KeyboardInterrupt:
            self.stop()


def run(config=None):
    """Run the web adapter and autonomy daemon as isolated OS processes."""
    from ada.infrastructure.runtime.daemon import run as run_daemon
    from ada.interfaces.web.server import main as run_web

    supervisor = ServiceSupervisor({"web": run_web, "autonomy": partial(run_daemon, config)})
    supervisor.start()
    supervisor.wait()
