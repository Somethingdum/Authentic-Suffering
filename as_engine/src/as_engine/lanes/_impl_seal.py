"""Bodies of lanes/seal.py (D-104)."""

from __future__ import annotations

import ipaddress
import os
import socket
import threading
from urllib.parse import urlsplit

from .seal import HOME_SUFFIXES, SealedError, SealError

_LOCK = threading.Lock()
_STATE = {"on": False, "names": frozenset(), "ips": set(), "refused": [], "orig": None, "env": None}
ENV_ON = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
          "HF_HUB_DISABLE_TELEMETRY": "1", "ANONYMIZED_TELEMETRY": "False", "DO_NOT_TRACK": "1"}
ENV_OFF = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def _ip(host):
    try:
        return ipaddress.ip_address(host.strip("[]").split("%")[0])
    except ValueError:
        return None


def _loopback(ip):
    return ip.is_loopback or (ip.version == 6 and ip.ipv4_mapped is not None and ip.ipv4_mapped.is_loopback)


def _home(ip):
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return _loopback(ip) or ip.is_private or ip.is_link_local


def _local_name(h):
    return h == "localhost" or h.endswith(".localhost")


def home_host(host: str) -> bool:
    h = (host or "").strip().lower().rstrip(".")
    if not h:
        return False
    ip = _ip(h)
    if ip is not None:
        return _home(ip) and not ip.is_unspecified
    if _local_name(h):
        return True
    return h.endswith(HOME_SUFFIXES) or ("." not in h and h.replace("-", "").isalnum())


def check_lane_url(url: str) -> str:
    parts = urlsplit(url or "")
    host = parts.hostname or ""
    if parts.scheme not in ("http", "https") or not host:
        raise SealError(f"{url!r} is not a model address (it should look like http://localhost:1234/v1).")
    if not home_host(host):
        raise SealError(f"{host} is outside this machine and its home network; the game only talks to models "
                        f"on your own machines.")
    return host.lower()


def _allowed_ip(ip):
    if _loopback(ip):
        return True
    return str(ip) in _STATE["ips"] and _home(ip)


def _addr_host(address):
    if isinstance(address, tuple) and address:
        return str(address[0])
    return None


def _refuse(host, port):
    with _LOCK:
        _STATE["refused"].append((host, port))
        del _STATE["refused"][:-100]
    raise SealedError(f"sealed: {host}:{port} is not one of your own machines")


def _guard_connect(sock, address):
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return
    host = _addr_host(address)
    port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
    ip = _ip(host) if host is not None else None
    if ip is None:
        hl = (host or "").lower().rstrip(".")
        if hl and (_local_name(hl) or hl in _STATE["names"]):
            return          # a name connect resolves in C; only the allowed names get this far
        _refuse(host, port)
    if not _allowed_ip(ip):
        _refuse(host, port)


def _install_hooks():
    orig = {"getaddrinfo": socket.getaddrinfo, "connect": socket.socket.connect,
            "connect_ex": socket.socket.connect_ex, "create_connection": socket.create_connection}
    _STATE["orig"] = orig

    def getaddrinfo(host, port, *a, **kw):
        if _STATE["on"] and host is not None:
            h = host.decode() if isinstance(host, bytes) else str(host)
            hl = h.lower().rstrip(".")
            ip = _ip(hl)
            if ip is None and not _local_name(hl) and hl not in _STATE["names"]:
                with _LOCK:
                    _STATE["refused"].append((h, port))
                    del _STATE["refused"][:-100]
                raise socket.gaierror(socket.EAI_NONAME, f"sealed: {h} is not one of your own machines")
            res = orig["getaddrinfo"](host, port, *a, **kw)
            if ip is None and hl in _STATE["names"]:
                with _LOCK:
                    for r in res:
                        addr = _ip(str(r[4][0]))
                        if addr is not None and _home(addr):
                            _STATE["ips"].add(str(addr))
            return res
        return orig["getaddrinfo"](host, port, *a, **kw)

    def connect(self, address):
        if _STATE["on"]:
            _guard_connect(self, address)
        return orig["connect"](self, address)

    def connect_ex(self, address):
        if _STATE["on"]:
            _guard_connect(self, address)
        return orig["connect_ex"](self, address)

    def create_connection(address, *a, **kw):
        if _STATE["on"]:
            host, port = address[0], address[1]
            ip = _ip(str(host))
            if ip is not None and not _allowed_ip(ip):
                _refuse(str(host), port)
        return orig["create_connection"](address, *a, **kw)

    socket.getaddrinfo = getaddrinfo
    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.create_connection = create_connection
    # asyncio's own connect paths (the Windows proactor uses ConnectEx, not socket.connect)
    import asyncio.proactor_events as _pe
    import asyncio.selector_events as _se
    for cls in (_se.BaseSelectorEventLoop, _pe.BaseProactorEventLoop):
        orig[cls] = cls.sock_connect

        def sock_connect(self, sock, address, _o=orig[cls]):
            if _STATE["on"]:
                _guard_connect(sock, address)
            return _o(self, sock, address)
        cls.sock_connect = sock_connect


def install(hosts=()) -> None:
    names, ips = set(), set()
    for h in hosts:
        hl = check_lane_url(h) if "://" in str(h) else str(h).strip().lower().rstrip(".")
        if not home_host(hl):
            raise SealError(f"{hl} is outside this machine and its home network; the game only talks to models "
                            f"on your own machines.")
        ip = _ip(hl)
        if ip is not None:
            ips.add(str(ip))
        else:
            names.add(hl)
    with _LOCK:
        if _STATE["orig"] is None:
            _install_hooks()
        if _STATE["env"] is None:
            _STATE["env"] = {k: os.environ.get(k) for k in (*ENV_ON, *ENV_OFF)}
        _STATE["names"] = frozenset(names)
        _STATE["ips"] = ips
        _STATE["refused"] = []
        _STATE["on"] = True
    os.environ.update(ENV_ON)
    for k in ENV_OFF:
        os.environ.pop(k, None)


def install_from_config(config) -> None:
    install([lane.base_url for _, lane in sorted(config.lanes.items(), key=lambda kv: str(kv[0]))])


def uninstall() -> None:
    with _LOCK:
        _STATE["on"] = False
        env, _STATE["env"] = _STATE["env"], None
    for k, v in (env or {}).items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def sealed() -> bool:
    return bool(_STATE["on"])


def refused() -> list[tuple[str, object]]:
    with _LOCK:
        return list(_STATE["refused"])


def allowed() -> dict[str, list[str]]:
    with _LOCK:
        return {"names": sorted(_STATE["names"]), "ips": sorted(_STATE["ips"])}
