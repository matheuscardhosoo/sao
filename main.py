"""
Underworld - Master Orchestrator
Starts the FastAPI server, spawns autonomous agents, and launches the visualizer / dashboard.
"""

import argparse
import os
import random
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent

HEURISTIC_AGENTS = [
    ("scout", "explorer"),
    ("scavenger", "scavenger"),
    ("philosopher", "social"),
    ("guardian", "guardian"),
]

LLM_AGENTS = [
    ("brave_explorer", "The Brave Explorer, focused on finding resources (!) to gain energy."),
    ("social_philosopher", "The Social Philosopher, focused on talking and leaving messages for others."),
    ("territorial_guardian", "The Territorial Guardian, focused on guarding a specific area and patrolling it."),
]


def wait_for_server(base_url: str, timeout: float = 15.0) -> bool:
    """Poll until server responds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"{base_url}/world/state", timeout=2)
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.3)
    return False


def spawn_agent(base_url: str, agent_id: str, personality: str = "") -> bool:
    """Spawn an agent at a random available position."""
    for _ in range(50):
        x, y = random.randint(2, 17), random.randint(2, 17)
        try:
            r = requests.post(
                f"{base_url}/spawn",
                json={"agent_id": agent_id, "x": x, "y": y, "personality": personality},
                timeout=2,
            )
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Underworld Simulation Master Orchestrator")
    parser.add_argument(
        "--mode",
        choices=["simple", "llm", "mixed"],
        default="simple",
        help="Agent brain mode: simple (100%% offline heuristic), llm, or mixed (default: simple)",
    )
    parser.add_argument(
        "--backend",
        choices=["ollama", "openai"],
        default="ollama",
        help="LLM backend if using --mode llm or mixed (default: ollama)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "7788")),
        help="API and Dashboard port (default: 7788)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server bind host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--no-visualizer",
        action="store_true",
        help="Run without terminal visualizer (headless or web-only)",
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Automatically open web dashboard in browser upon launch",
    )
    args = parser.parse_args()

    port = args.port
    host = args.host
    base_url = f"http://{host}:{port}"

    print("==================================================")
    print("  🌌 UNDERWORLD SIMULATION SYSTEM")
    print(f"  Mode: {args.mode.upper()} | Port: {port}")
    print(f"  Web Dashboard: {base_url}/dashboard")
    print("==================================================")

    # 1. Start FastAPI server in background
    server_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", host, "--port", str(port)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not wait_for_server(base_url):
        print("❌ Server failed to start")
        server_proc.terminate()
        return 1

    print(f"✅ Server online at {base_url}")

    if args.web:
        webbrowser.open(f"{base_url}/dashboard")

    # 2. Launch Agents according to mode
    agent_procs: list[subprocess.Popen] = []

    if args.mode in ("simple", "mixed"):
        agents_to_spawn = HEURISTIC_AGENTS if args.mode == "simple" else HEURISTIC_AGENTS[:2]
        for aid, vibe in agents_to_spawn:
            if spawn_agent(base_url, aid, personality=f"Heuristic {vibe}"):
                proc = subprocess.Popen(
                    [
                        sys.executable,
                        str(ROOT / "src" / "agents" / "agent_simple.py"),
                        "--agent-id", aid,
                        "--vibe", vibe,
                        "--api-url", base_url,
                    ],
                    cwd=ROOT,
                    env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                agent_procs.append(proc)
        print(f"🤖 Spawned {len(agent_procs)} heuristic autonomous agents ({[a[0] for a in agents_to_spawn]})")

    if args.mode in ("llm", "mixed"):
        llm_list = LLM_AGENTS if args.mode == "llm" else LLM_AGENTS[:1]
        for name, personality in llm_list:
            if spawn_agent(base_url, name, personality=personality):
                proc = subprocess.Popen(
                    [
                        sys.executable,
                        str(ROOT / "src" / "agents" / "agent_llm.py"),
                        "--name", name,
                        "--personality", personality,
                        "--backend", args.backend,
                        "--api_url", base_url,
                    ],
                    cwd=ROOT,
                    env={
                        **os.environ,
                        "PYTHONPATH": str(ROOT / "src"),
                        "UNDERWORLD_API_URL": base_url,
                    },
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                agent_procs.append(proc)
        print(f"🧠 Spawned {len(llm_list)} LLM agents via {args.backend}")

    # 3. Launch visualizer or wait
    if not args.no_visualizer:
        print("📺 Launching terminal visualizer (Press Ctrl+C to stop)...")
        try:
            subprocess.run(
                [sys.executable, str(ROOT / "src" / "visualizer.py"), "--no-curses"],
                cwd=ROOT,
                env={
                    **os.environ,
                    "PYTHONPATH": str(ROOT / "src"),
                    "UNDERWORLD_API_URL": base_url,
                },
            )
        except KeyboardInterrupt:
            pass
    else:
        print("🚀 Running in headless/web mode. Dashboard live at:")
        print(f"   {base_url}/dashboard")
        print("Press Ctrl+C to terminate.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    # Cleanup
    print("\n🛑 Shutting down Underworld...")
    for p in agent_procs:
        p.terminate()
    server_proc.terminate()

    for p in agent_procs + [server_proc]:
        try:
            p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            p.kill()

    print("👋 Shutdown complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
