"""The seal (P12, D-104; the owner's hard rule): nothing leaves the owner's own machines.

The owner: "I need this to be a completely sealed up, local build that doesn't put my privacy at
risk"; "No limitations. No privacy leaks. Hard rule." Rules SEAL-01..05.

The game talks to the language models on the owner's own machines (02 §2: the desktop and, for Lane
B, the laptop) and to nothing else. The seal is process-wide: once installed, every outbound
connection and every name lookup in the process — the engine's, Talemate's, any library's — passes
through it, so a library that would phone home fails as if the network were down.

home_host(host) -> bool
  True for loopback ('localhost', '*.localhost', 127.0.0.0/8, ::1) and for the owner's own network:
  a private or link-local address (10/8, 172.16/12, 192.168/16, 169.254/16, fc00::/7, fe80::/10) or
  a name that is a single label ('laptop') or ends in HOME_SUFFIXES. The unspecified address (0.0.0.0,
  ::) is not a host.

SEAL-01 check_lane_url(url) -> the host, lower case
  A lane's base_url is http(s) to a home_host; anything else raises SealError (a ValueError): not
  http(s) or no host -> "{url!r} is not a model address (it should look like
  http://localhost:1234/v1)."; a host outside -> "{host} is outside this machine and its home
  network; the game only talks to models on your own machines." contracts.settings.LaneConfig
  checks its base_url with it, so a config naming a model anywhere else never loads and a
  config_set that names one is refused.

SEAL-02 install(hosts) -> None
  hosts: lane base_urls or bare host names. Each must be a home_host (SealError otherwise, and nothing
  changes). Process-wide, hooked once (later calls replace the allowed set and clear refused()):
    socket.getaddrinfo(host, …) for a name that is not an IP literal, not 'localhost'/'*.localhost'
      and not one of hosts raises socket.gaierror(EAI_NONAME, "sealed: {host} is not one of your own
      machines") WITHOUT asking DNS (a lookup leaks the name too); for one of hosts the answer's home
      addresses are remembered as allowed.
    socket.socket.connect / connect_ex, socket.create_connection and the event loops' sock_connect
      (selector and proactor: Windows' default loop connects with ConnectEx, not socket.connect) to
      an AF_INET/AF_INET6 address that is not loopback and not an allowed home address (hosts' IP
      literals and the remembered ones) raise SealedError (a ConnectionRefusedError) "sealed:
      {host}:{port} is not one of your own machines". Unix sockets pass.
  Every refusal is kept in refused() as (host, port), the last 100.
SEAL-03 install also sets, overriding: HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1,
  HF_DATASETS_OFFLINE=1, HF_HUB_DISABLE_TELEMETRY=1, ANONYMIZED_TELEMETRY=False, DO_NOT_TRACK=1; and
  removes HTTP_PROXY, HTTPS_PROXY, ALL_PROXY (both cases) — a proxy would carry the game's words off
  the machine. uninstall() lifts the seal and puts those variables back as they were.
install_from_config(config) -> None: install with every lane's base_url (sorted by lane).
sealed() -> bool; refused() -> list[(host, port)]; allowed() -> {'names': sorted allowed host names,
'ips': sorted allowed home addresses (the hosts' IP literals and the remembered ones)} — loopback is
always allowed and is not listed.

SEAL-04 Where it is installed: the Talemate server before anything else starts
  (src/talemate/server/run.py, 02 §4.1, from as_config.yaml through config_loader; loopback only
  when there is none), the as-engine CLI (every command), and GameService.on_config_set (a changed
  lane address re-seals with the new hosts). lanes.transport.HttpTransport's client never reads
  proxies from the environment (trust_env False).
SEAL-05 Nothing reaches out on its own: the launchers bind 127.0.0.1 (never 0.0.0.0) and run uv
  offline without syncing; docker-compose publishes on 127.0.0.1 only; the frontend loads no font,
  script or style from outside (no Google Fonts; the system font is used).
"""

from __future__ import annotations

from collections.abc import Iterable

HOME_SUFFIXES = (".local", ".lan", ".home.arpa", ".internal")


class SealError(ValueError):
    """A model address outside the owner's machines."""


class SealedError(ConnectionRefusedError):
    """A connection the seal refused."""


def home_host(host: str) -> bool:
    raise NotImplementedError("P12")


def check_lane_url(url: str) -> str:
    raise NotImplementedError("P12")


def install(hosts: Iterable[str] = ()) -> None:
    raise NotImplementedError("P12")


def install_from_config(config) -> None:
    raise NotImplementedError("P12")


def uninstall() -> None:
    raise NotImplementedError("P12")


def sealed() -> bool:
    raise NotImplementedError("P12")


def refused() -> list[tuple[str, object]]:
    raise NotImplementedError("P12")


def allowed() -> dict[str, list[str]]:
    raise NotImplementedError("P12")


from ._impl_seal import (  # noqa
    allowed,
    check_lane_url,
    home_host,
    install,
    install_from_config,
    refused,
    sealed,
    uninstall,
)
