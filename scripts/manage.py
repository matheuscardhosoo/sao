#!/usr/bin/env python3
"""
Underworld (SAO) - Unified Operations & Automation CLI
Performs repetitive tasks: running server, spawning agents, training policies,
benchmarking, adding resources, and checking simulation status.
"""

import argparse
import os
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

API_URL = os.environ.get("UNDERWORLD_API_URL", "http://127.0.0.1:7788")
PY = sys.executable


def get_requests():
    import requests
    return requests


def cmd_status(args):
    """Display real-time simulation state from the API."""
    requests = get_requests()
    try:
        r = requests.get(f"{API_URL}/world/state", timeout=3)
        if r.status_code != 200:
            print(f"❌ Server returned HTTP {r.status_code}")
            return
        data = r.json()
    except Exception as e:
        print(f"❌ Could not connect to Underworld server at {API_URL}: {e}")
        print("💡 Start the server first with: python manage.py server")
        return

    agents = data.get("agent_details", {})
    events = data.get("event_log", [])

    print("=" * 64)
    print(f"🌌 UNDERWORLD SIMULATION STATUS ({API_URL})")
    print("=" * 64)
    print(f"Active Entities: {len(agents)}")
    print("-" * 64)

    if not agents:
        print("No active agents spawned yet.")
    else:
        print(f"{'Agent ID':<18} | {'Status':<9} | {'Energy':<8} | {'Crystals':<9} | {'Position'}")
        print("-" * 64)
        for aid, a in agents.items():
            status = "ACTIVE" if a.get("is_active") else "EXHAUSTED"
            pos = f"({a.get('x')}, {a.get('y')})"
            energy = f"{a.get('energy')}/100"
            crystals = a.get("inventory_count", 0)
            print(f"{aid:<18} | {status:<9} | {energy:<8} | {crystals:<9} | {pos}")

    print("\nRecent Simulation Events:")
    print("-" * 64)
    for e in events[-6:]:
        print(f"  • {e}")
    print("=" * 64)
    print(f"Web Dashboard: {API_URL}/dashboard")


def cmd_spawn(args):
    """Spawn an agent into the live simulation and launch its process."""
    requests = get_requests()
    x = args.x if args.x is not None else random.randint(2, 17)
    y = args.y if args.y is not None else random.randint(2, 17)

    # 1. Register spawn via API
    try:
        r = requests.post(
            f"{API_URL}/spawn",
            json={"agent_id": args.id, "x": x, "y": y, "personality": f"{args.type} {args.vibe}"},
            timeout=3,
        )
        if r.status_code != 200:
            print(f"❌ Failed to spawn agent '{args.id}': {r.text}")
            return
        print(f"✅ Registered agent '{args.id}' at ({x}, {y})")
    except Exception as e:
        print(f"❌ Error communicating with API: {e}")
        return

    # 2. Launch process
    if args.type == "trained":
        cmd = [
            PY,
            str(ROOT / "src" / "agents" / "agent_trained.py"),
            "--agent-id", args.id,
            "--api-url", API_URL,
            "--interval", str(args.interval),
        ]
    elif args.type == "llm":
        cmd = [
            PY,
            str(ROOT / "src" / "agents" / "agent_llm.py"),
            "--name", args.id,
            "--personality", args.vibe,
            "--api_url", API_URL,
            "--backend", args.backend,
        ]
    else:  # heuristic
        cmd = [
            PY,
            str(ROOT / "src" / "agents" / "agent_simple.py"),
            "--agent-id", args.id,
            "--vibe", args.vibe,
            "--api-url", API_URL,
            "--interval", str(args.interval),
        ]

    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": f"{ROOT}:{ROOT}/src"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"🤖 Launched {args.type.upper()} agent process (PID: {proc.pid})")


def cmd_spawn_team(args):
    """Spawn a complete balanced ecosystem of agents."""
    team = [
        ("trained_oracle", "trained", "trained_q_agent"),
        ("scout_alpha", "heuristic", "explorer"),
        ("scavenger_beta", "heuristic", "scavenger"),
        ("philosopher_gamma", "heuristic", "social"),
        ("guardian_delta", "heuristic", "guardian"),
    ]

    print("🚀 Spawning balanced autonomous agent team into Underworld...")
    for aid, atype, vibe in team:
        ns = argparse.Namespace(
            id=aid,
            type=atype,
            vibe=vibe,
            x=None,
            y=None,
            interval=0.9,
            backend="ollama",
        )
        cmd_spawn(ns)
        time.sleep(0.2)
    print("\n✅ Team spawned! Check dashboard: " + f"{API_URL}/dashboard")


def cmd_train(args):
    """Run offline Q-Learning trainer."""
    cmd = [
        PY,
        str(ROOT / "scripts" / "train.py"),
        "--episodes", str(args.episodes),
        "--max-steps", str(args.steps),
    ]
    subprocess.run(cmd, cwd=ROOT, env={**os.environ, "PYTHONPATH": f"{ROOT}:{ROOT}/src"})


def cmd_benchmark(args):
    """Run agent policy benchmark."""
    cmd = [
        PY,
        str(ROOT / "scripts" / "benchmark.py"),
        "--trials", str(args.trials),
        "--max-steps", str(args.steps),
    ]
    subprocess.run(cmd, cwd=ROOT, env={**os.environ, "PYTHONPATH": f"{ROOT}:{ROOT}/src"})


def cmd_add_resource(args):
    """Manually add an energy crystal to the world."""
    requests = get_requests()
    x = args.x if args.x is not None else random.randint(0, 19)
    y = args.y if args.y is not None else random.randint(0, 19)
    try:
        r = requests.post(f"{API_URL}/add_resource", json={"x": x, "y": y}, timeout=3)
        if r.status_code == 200:
            print(f"✨ Energy crystal added at ({x}, {y})")
        else:
            print(f"❌ Failed: {r.text}")
    except Exception as e:
        print(f"❌ Error: {e}")


def cmd_kill_all(args):
    """Kill running background agent processes."""
    print("🛑 Terminating background agent processes...")
    import subprocess
    cmd = "pkill -f 'src/agents/' || true"
    subprocess.run(cmd, shell=True)
    print("✅ Stopped all agent background processes.")


def cmd_server(args):
    """Launch the main orchestrator or web dashboard."""
    cmd = [PY, str(ROOT / "main.py")]
    if args.no_visualizer:
        cmd.append("--no-visualizer")
    if args.web:
        cmd.append("--web")
    if args.mode:
        cmd.extend(["--mode", args.mode])

    subprocess.run(cmd, cwd=ROOT, env={**os.environ, "PYTHONPATH": f"{ROOT}:{ROOT}/src"})


def main():
    parser = argparse.ArgumentParser(description="Underworld Simulation Automation CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    p_status = subparsers.add_parser("status", help="Show live simulation state and active agents")
    p_status.set_defaults(func=cmd_status)

    # server
    p_server = subparsers.add_parser("server", help="Start simulation server & dashboard")
    p_server.add_argument("--web", action="store_true", help="Open web dashboard in browser")
    p_server.add_argument("--no-visualizer", action="store_true", help="Headless mode")
    p_server.add_argument("--mode", choices=["simple", "llm", "mixed"], default="simple")
    p_server.set_defaults(func=cmd_server)

    # spawn
    p_spawn = subparsers.add_parser("spawn", help="Spawn an agent into the running simulation")
    p_spawn.add_argument("id", help="Unique agent identifier")
    p_spawn.add_argument("--type", choices=["trained", "heuristic", "llm"], default="trained")
    p_spawn.add_argument("--vibe", default="scavenger", help="Vibe/archetype (explorer, scavenger, social, guardian, aggressive)")
    p_spawn.add_argument("--x", type=int, default=None)
    p_spawn.add_argument("--y", type=int, default=None)
    p_spawn.add_argument("--interval", type=float, default=0.8)
    p_spawn.add_argument("--backend", default="ollama")
    p_spawn.set_defaults(func=cmd_spawn)

    # spawn-team
    p_team = subparsers.add_parser("spawn-team", help="Spawn a balanced team of 5 diverse agents")
    p_team.set_defaults(func=cmd_spawn_team)

    # train
    p_train = subparsers.add_parser("train", help="Train reinforcement learning agent policy")
    p_train.add_argument("--episodes", type=int, default=3000)
    p_train.add_argument("--steps", type=int, default=200)
    p_train.set_defaults(func=cmd_train)

    # benchmark
    p_bench = subparsers.add_parser("benchmark", help="Benchmark agent architectures")
    p_bench.add_argument("--trials", type=int, default=20)
    p_bench.add_argument("--steps", type=int, default=200)
    p_bench.set_defaults(func=cmd_benchmark)

    # add-resource
    p_res = subparsers.add_parser("add-resource", help="Add energy crystal at (x, y)")
    p_res.add_argument("--x", type=int, default=None)
    p_res.add_argument("--y", type=int, default=None)
    p_res.set_defaults(func=cmd_add_resource)

    # kill-all
    p_kill = subparsers.add_parser("kill-all", help="Stop all background agent processes")
    p_kill.set_defaults(func=cmd_kill_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
