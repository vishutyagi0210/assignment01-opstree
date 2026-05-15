"""
Orch - A lightweight container orchestrator
Usage: python orch.py -f app.yml
"""

import argparse
import signal
import sys
import threading
import time

import docker
import requests
import yaml


# ─────────────────────────────────────────────
# COLORS for terminal output
# ─────────────────────────────────────────────
class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def log(level, msg):
    colors = {"INFO": Color.CYAN, "OK": Color.GREEN, "WARN": Color.YELLOW, "ERR": Color.RED}
    color = colors.get(level, Color.RESET)
    timestamp = time.strftime("%H:%M:%S")
    print(f"  {color}[{level}]{Color.RESET} {timestamp}  {msg}")


# ─────────────────────────────────────────────
# YAML CONFIG PARSER
# ─────────────────────────────────────────────
def parse_config(file_path):
    """Read and validate the YAML config file."""
    with open(file_path, "r") as f:
        config = yaml.safe_load(f)

    svc = config.get("service", {})
    required = ["name", "image", "replicas", "ports"]
    for key in required:
        if key not in svc:
            print(f"{Color.RED}ERROR: Missing required field 'service.{key}' in {file_path}{Color.RESET}")
            sys.exit(1)

    if len(svc["ports"]) < svc["replicas"]:
        print(f"{Color.RED}ERROR: Not enough port mappings for {svc['replicas']} replicas. "
              f"You defined {len(svc['ports'])} ports.{Color.RESET}")
        sys.exit(1)

    return svc


# ─────────────────────────────────────────────
# CONTAINER MANAGER
# ─────────────────────────────────────────────
class Orchestrator:
    def __init__(self, config):
        self.config = config
        self.client = docker.from_env()
        self.service_name = config["name"]
        self.image = config["image"]
        self.replicas = config["replicas"]
        self.ports = config["ports"]  # e.g. ["8081:8080", "8082:8080"]
        self.healthcheck = config.get("healthcheck", {})
        self.containers = {}  # {replica_index: container_object}
        self.running = True

    def start(self):
        """Create and start all replica containers."""
        print()
        log("INFO", f"{Color.BOLD}Starting orchestrator for '{self.service_name}'{Color.RESET}")
        log("INFO", f"Image: {self.image}  |  Replicas: {self.replicas}")
        print()

        for i in range(self.replicas):
            self._create_replica(i)

        print()
        log("OK", f"All {self.replicas} replicas are running!")
        self._print_status()

    def _create_replica(self, index):
        """Create and start a single replica container."""
        host_port, container_port = self.ports[index].split(":")
        container_name = f"{self.service_name}-replica-{index + 1}"

        # Remove existing container with same name if any
        try:
            old = self.client.containers.get(container_name)
            log("WARN", f"Removing stale container: {container_name}")
            old.remove(force=True)
        except docker.errors.NotFound:
            pass

        # Create and start the container
        container = self.client.containers.run(
            image=self.image,
            name=container_name,
            ports={f"{container_port}/tcp": int(host_port)},
            detach=True,
            labels={
                "managed-by": "orch",
                "orch.service": self.service_name,
                "orch.replica-index": str(index),
            },
        )

        self.containers[index] = container
        log("OK", f"Started {container_name}  →  localhost:{host_port} → :{container_port}")
        return container

    def _print_status(self):
        """Print a status table of all replicas."""
        print()
        print(f"  {'─' * 55}")
        print(f"  {'REPLICA':<25} {'PORT':<15} {'STATUS':<15}")
        print(f"  {'─' * 55}")
        for i, container in self.containers.items():
            host_port = self.ports[i].split(":")[0]
            container.reload()
            status = container.status
            color = Color.GREEN if status == "running" else Color.RED
            name = f"{self.service_name}-replica-{i + 1}"
            print(f"  {name:<25} {host_port:<15} {color}{status}{Color.RESET}")
        print(f"  {'─' * 55}")
        print()

    # ─────────────────────────────────────────
    # SELF-HEALING (Health Monitor)
    # ─────────────────────────────────────────
    def start_health_monitor(self):
        """Start a background thread that monitors container health."""
        endpoint = self.healthcheck.get("endpoint", "/healthcheck")
        interval = self.healthcheck.get("interval", 10)
        max_retries = self.healthcheck.get("retries", 3)
        failure_counts = {i: 0 for i in range(self.replicas)}

        log("INFO", f"Health monitor started  |  endpoint: {endpoint}  |  interval: {interval}s")
        print()

        while self.running:
            time.sleep(interval)
            if not self.running:
                break

            for i in range(self.replicas):
                if not self.running:
                    break

                host_port = self.ports[i].split(":")[0]
                container_name = f"{self.service_name}-replica-{i + 1}"
                healthy = False

                # Check 1: Is the container still running?
                try:
                    container = self.containers.get(i)
                    if container:
                        container.reload()
                        if container.status != "running":
                            raise Exception(f"Container status: {container.status}")
                    else:
                        raise Exception("Container not found in tracker")
                except Exception:
                    log("ERR", f"{container_name} is DOWN — container not running")
                    failure_counts[i] = max_retries  # force immediate heal
                    self._heal(i, failure_counts)
                    continue

                # Check 2: Does the healthcheck endpoint respond?
                try:
                    url = f"http://localhost:{host_port}{endpoint}"
                    resp = requests.get(url, timeout=3)
                    if resp.status_code == 200:
                        healthy = True
                        failure_counts[i] = 0
                except Exception:
                    healthy = False

                if not healthy:
                    failure_counts[i] += 1
                    log("WARN", f"{container_name} healthcheck FAILED ({failure_counts[i]}/{max_retries})")

                    if failure_counts[i] >= max_retries:
                        self._heal(i, failure_counts)

    def _heal(self, index, failure_counts):
        """Kill unhealthy container and restart it (self-healing)."""
        container_name = f"{self.service_name}-replica-{index + 1}"
        log("ERR", f"SELF-HEALING: Restarting {container_name}...")

        # Kill old container
        try:
            old = self.containers.get(index)
            if old:
                old.remove(force=True)
        except Exception:
            # Container might already be gone
            try:
                old = self.client.containers.get(container_name)
                old.remove(force=True)
            except docker.errors.NotFound:
                pass

        # Start fresh
        self._create_replica(index)
        failure_counts[index] = 0
        log("OK", f"HEALED: {container_name} is back up!")

    # ─────────────────────────────────────────
    # GRACEFUL SHUTDOWN
    # ─────────────────────────────────────────
    def shutdown(self):
        """Stop and remove all managed containers."""
        self.running = False
        print()
        log("WARN", f"{Color.BOLD}Shutting down orchestrator...{Color.RESET}")

        for i, container in self.containers.items():
            name = f"{self.service_name}-replica-{i + 1}"
            try:
                container.remove(force=True)
                log("OK", f"Stopped {name}")
            except Exception:
                log("WARN", f"{name} already removed")

        log("OK", "All containers stopped. Goodbye!")
        print()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Orch — A lightweight container orchestrator",
        usage="python orch.py -f app.yml",
    )
    parser.add_argument("-f", "--file", required=True, help="Path to YAML config file")
    args = parser.parse_args()

    # Parse config
    config = parse_config(args.file)

    # Create orchestrator
    orch = Orchestrator(config)

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        orch.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start all containers
    orch.start()

    # Start health monitor in background
    monitor_thread = threading.Thread(target=orch.start_health_monitor, daemon=True)
    monitor_thread.start()

    log("INFO", "Orchestrator is running. Press Ctrl+C to stop.")
    print()

    # Keep main thread alive
    while orch.running:
        time.sleep(1)


if __name__ == "__main__":
    main()
