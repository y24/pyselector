from __future__ import annotations

import json
from argparse import Namespace

from pyselector import __version__
from pyselector.server import state as state_module
from pyselector.server.client import ServerClient
from pyselector.server.protocol import CONTROL_STOP, PROTOCOL_VERSION, Request
from pyselector.server.server import Server
from pyselector.utils.errors import EXIT_OK, EXIT_UNEXPECTED
from pyselector.utils.logging import info_log

STOP_TIMEOUT_SECONDS = 5.0


def run_serve(args: Namespace) -> int:
    if getattr(args, "status", False):
        return _run_status(args)
    if getattr(args, "stop", False):
        return _run_stop(args)
    return _run_foreground(args)


def _run_foreground(args: Namespace) -> int:
    from pyselector.server.pipe import NamedPipeTransport, PipeUnavailableError

    idle_timeout = getattr(args, "idle_timeout", 300)
    allow_actions = getattr(args, "allow_actions", False)
    running = state_module.read_live_state()
    if running is not None:
        print(
            f"[ERROR] 常駐サーバーは既に動作しています (pid {running.pid})。"
            "停止するには pyselector serve --stop を実行してください",
            file=_stderr(),
        )
        return EXIT_UNEXPECTED

    transport = NamedPipeTransport()
    server = Server(
        transport,
        idle_timeout=idle_timeout,
        allow_actions=allow_actions,
        max_refs=getattr(args, "max_refs", 5000),
    )
    try:
        transport.listen()
    except PipeUnavailableError as exc:
        print(f"[ERROR] {exc}", file=_stderr())
        return EXIT_UNEXPECTED

    info_log(f"pyselector serve started (instance {server.instance_id}, pipe {transport.name})")
    info_log(f"idle timeout {idle_timeout}s / act {'allowed' if allow_actions else 'refused'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        info_log("停止要求を受け取りました。")
    info_log("pyselector serve stopped")
    return EXIT_OK


def _run_status(args: Namespace) -> int:
    state = state_module.read_live_state()
    json_output = getattr(args, "json", False)
    if state is None:
        if json_output:
            print(_dump({"running": False}), end="")
        else:
            print("[INFO] 常駐サーバーは動作していません。")
        return 1
    if json_output:
        payload = dict(state.to_dict())
        payload["running"] = True
        print(_dump(payload), end="")
    else:
        print(f"[INFO] 常駐サーバーは動作しています。 pid={state.pid} instance={state.instance_id}")
        print(f"[INFO] pipe={state.pipe}")
        print(f"[INFO] version={state.version} started_at={state.started_at}")
        print(f"[INFO] act={'allowed' if state.allow_actions else 'refused'} idle_timeout={state.idle_timeout}s")
    return EXIT_OK


def _run_stop(args: Namespace) -> int:
    json_output = getattr(args, "json", False)
    state = state_module.read_live_state()
    if state is None:
        if json_output:
            print(_dump({"stopped": False, "running": False}), end="")
        else:
            print("[INFO] 常駐サーバーは動作していません。")
        return 1
    response = ServerClient().send(
        Request(protocol=PROTOCOL_VERSION, version=__version__, control=CONTROL_STOP),
        STOP_TIMEOUT_SECONDS,
    )
    stopped = response is not None and not response.rejected
    if json_output:
        print(_dump({"stopped": stopped, "running": True, "pid": state.pid}), end="")
    elif stopped:
        print(f"[INFO] 常駐サーバーに停止を要求しました。 pid={state.pid}")
    else:
        print("[ERROR] 常駐サーバーに停止を要求できませんでした。", file=_stderr())
    return EXIT_OK if stopped else EXIT_UNEXPECTED


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _stderr():
    import sys

    return sys.stderr
