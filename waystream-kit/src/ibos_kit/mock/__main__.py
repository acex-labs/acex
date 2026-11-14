import argparse
import asyncio
import logging

from ibos_kit import evidence
from ibos_kit.mock.scenarios import CREDENTIALS, LETTERS, SCENARIOS, device_for
from ibos_kit.mock.server import RunningMock


def explain(key: str) -> str:
    device = device_for(key)
    register = evidence.load()
    facts = {fact for c in device.profile.commands for fact in c.facts} | set(device.profile.assumptions)
    facts |= {"PROMPT-MODES", "ENABLE-COMMAND", "TERMINAL-COMMANDS", "COMMAND-ABBREVIATION", "ERROR-FORMAT"}
    facts |= {"LOGIN-LANDING-MODE", "PROMPT-TRAILING-SPACE", "SSH-AUTH-METHODS", "LINE-ENDINGS-ANSI"}
    if device.profile.enable_password:
        facts.add("ENABLE-WRONG-PASSWORD")
    rows = sorted((register.facts[f] for f in facts), key=lambda f: (evidence.LEVELS.index(f.level), f.id))
    lines = [f"{device.profile.title}", f"login: {CREDENTIALS['username']} / {CREDENTIALS['password']} (synthetic)", ""]
    lines += [f"  {'assumed' if f.assumed else f.level.lower():9} {f.level:9} {f.id}" for f in rows]
    lines += ["", "assumed = the mock answers anyway; a passing test proves nothing about a real device."]
    return "\n".join(lines)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m ibos_kit.mock", description="A synthetic Waystream iBOS over SSH.")
    p.add_argument("scenario", nargs="?", help="a letter a-f or a full key; see --list")
    p.add_argument("--list", action="store_true", help="list the scenarios")
    p.add_argument("--explain", action="store_true", help="show which behaviours are verified and which are assumed")
    p.add_argument("--host", default="127.0.0.1", help="loopback addresses only")
    p.add_argument("--port", type=int, default=2222)
    p.add_argument("--start-mode", choices=["user", "privileged"])
    p.add_argument("--prompt-trailing-space", action="store_true")
    p.add_argument("--experimental-config-mode", action="store_true", help="UNVERIFIED configuration mode")
    p.add_argument("--latency-ms", type=int, default=0)
    p.add_argument("--hang-on", action="append", default=[], help="a command that never gets an answer")
    p.add_argument("--drop-after-lines", type=int, help="close the connection after N lines of show running-config")
    p.add_argument("--reject-logins", action="store_true")
    p.add_argument("--legacy-kex-only", action="store_true")
    return p


async def serve(args: argparse.Namespace) -> None:
    overrides = {
        "prompt_trailing_space": args.prompt_trailing_space,
        "experimental_config_mode": args.experimental_config_mode,
        "latency_ms": args.latency_ms,
        "hang_on": tuple(args.hang_on),
        "drop_after_lines": args.drop_after_lines,
        "reject_logins": args.reject_logins,
        "legacy_kex_only": args.legacy_kex_only,
    }
    if args.start_mode:
        overrides["start_mode"] = args.start_mode
    async with RunningMock(device_for(args.scenario, **overrides), host=args.host, port=args.port) as mock:
        print(f"{mock.device.profile.title}")
        print(f"listening on {mock.host}:{mock.port}")
        print(f"user {CREDENTIALS['username']}  password {CREDENTIALS['password']}")
        if mock.device.profile.enable_password:
            print(f"enable password {mock.device.profile.enable_password}")
        if args.experimental_config_mode:
            print("EXPERIMENTAL configuration mode is on: it is not verified iBOS behaviour")
        print("ctrl-c to stop")
        await asyncio.Event().wait()


def main() -> None:
    args = parser().parse_args()
    if args.list or not args.scenario:
        for letter, key in LETTERS.items():
            print(f"{letter}  {key:22} {SCENARIOS[key].title}")
        return
    if args.explain:
        print(explain(args.scenario))
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    try:
        asyncio.run(serve(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
