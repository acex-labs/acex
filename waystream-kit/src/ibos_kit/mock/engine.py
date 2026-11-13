import re
from dataclasses import dataclass

from ibos_kit import evidence
from ibos_kit.mock.scenarios import Command, Device
from ibos_kit.paths import DEVICE_FIXTURES

ALIASES = {"sh": "show", "int": "interface", "br": "brief"}
ERROR_PREFIX = "%-ERR: "
EXPERIMENTAL_BANNER = "% EXPERIMENTAL PROFILE: configuration mode in this mock is not verified iBOS behaviour."
ORDER = {"VERIFIED": 0, "INFERRED": 1, "UNKNOWN": 2}

SPECIALS = (
    Command(("enable",), facts=("ENABLE-COMMAND",)),
    Command(("exit",)),
    Command(("terminal", "no", "pager"), facts=("TERMINAL-COMMANDS",)),
    Command(("terminal", "width", "65535"), facts=("TERMINAL-COMMANDS",)),
)
CONFIG_ENTRY = Command(("configure", "terminal"), privileged=True, facts=("CONFIG-MODE-ENTRY",))


@dataclass
class Reply:
    text: str
    close: bool = False
    echo: bool = True
    prompt_follows: bool = True
    hang: bool = False
    drop: bool = False


@dataclass(frozen=True)
class TraceEntry:
    command: str
    facts: tuple[str, ...]
    level: str
    assumed: bool


class Session:
    def __init__(self, device: Device):
        self.device = device
        self.mode = device.profile.start_mode
        self.interface: str | None = None
        self.awaiting_enable_password = False
        self.trace: list[TraceEntry] = []

    @property
    def prompt(self) -> str:
        suffix = {"user": ">", "privileged": "#", "config": "(config)#", "config-if": "(config-if)#"}[self.mode]
        return f"{self.device.hostname}{suffix}{' ' if self.device.prompt_trailing_space else ''}"

    def greeting(self) -> str:
        banner = EXPERIMENTAL_BANNER + "\n" if self.device.experimental_config_mode else ""
        return banner + self.prompt

    def handle(self, line: str) -> Reply:
        if self.awaiting_enable_password:
            return self._enable_password(line)
        tokens = [(m.group(), m.start()) for m in re.finditer(r"\S+", line)]
        if not tokens:
            return Reply("")
        words = tuple(ALIASES.get(w, w) for w, _ in tokens)
        facts = ("COMMAND-ABBREVIATION",) if any(w in ALIASES for w, _ in tokens) else ()
        if self.device.faults.hang_on and " ".join(words) in self.device.faults.hang_on:
            return Reply("", hang=True)
        if self.mode in ("config", "config-if"):
            return self._configure(line.strip(), words, tokens)
        command = self._match(words)
        if command is None:
            return self._error(line.strip(), tokens, words)
        return self._run(command, words, facts)

    def _commands(self) -> list[Command]:
        privileged = self.mode == "privileged"
        commands = [c for c in self.device.profile.commands if privileged or not c.privileged]
        if self.device.experimental_config_mode and privileged:
            commands.append(CONFIG_ENTRY)
        return [*commands, *SPECIALS]

    def _match(self, words: tuple[str, ...]) -> Command | None:
        for command in self._commands():
            if len(command.words) == len(words) and all(
                c == w or (c == "<interface>" and w in self.device.profile.contexts)
                for c, w in zip(command.words, words, strict=True)
            ):
                return command
        return None

    def _error(self, line: str, tokens: list[tuple[str, int]], words: tuple[str, ...]) -> Reply:
        commands = self._commands()
        position = next(
            (i for i in range(len(words)) if not any(c.words[: i + 1] == words[: i + 1] for c in commands)),
            len(tokens) - 1,
        )
        word, start = tokens[position]
        self._record(line, ("ERROR-FORMAT",))
        return Reply(f"{ERROR_PREFIX}{line}\n{' ' * (len(ERROR_PREFIX) + start)}{'^' * len(word)} Invalid command")

    def _run(self, command: Command, words: tuple[str, ...], extra_facts: tuple[str, ...]) -> Reply:
        self._record(" ".join(words), command.facts + extra_facts)
        if command.words == ("exit",):
            return Reply("", close=True)
        if command.words == ("enable",):
            return self._enable()
        if command.words[0] == "terminal":
            return Reply("")
        if command.words == CONFIG_ENTRY.words:
            self.mode = "config"
            return Reply("")
        text = self.device.running_config if command.live_config else (DEVICE_FIXTURES / command.fixture).read_text()
        text = text.rstrip("\n")
        limit = self.device.faults.drop_after_lines
        if command.live_config and limit is not None:
            return Reply("\n".join(text.splitlines()[:limit]), drop=True, prompt_follows=False)
        return Reply(text)

    def _enable(self) -> Reply:
        if self.mode == "privileged":
            return Reply("")
        if self.device.profile.enable_password:
            self.awaiting_enable_password = True
            return Reply("Password:", echo=False, prompt_follows=False)
        self.mode = "privileged"
        return Reply("")

    def _enable_password(self, line: str) -> Reply:
        self.awaiting_enable_password = False
        if line == self.device.profile.enable_password:
            self.mode = "privileged"
            self._record("enable (password)", ("ENABLE-COMMAND",))
            return Reply("")
        self._record("enable (wrong password)", ("ENABLE-WRONG-PASSWORD",))
        return Reply("% Access denied")

    def _configure(self, line: str, words: tuple[str, ...], tokens: list[tuple[str, int]]) -> Reply:
        facts = ("CONFIG-MODE-ENTRY", "CONFIG-SAVE-COMMIT", "CONFIG-ERROR-FEEDBACK")
        device = self.device
        if words in (("end",), ("exit",)):
            self.mode = "privileged" if words == ("end",) or self.mode == "config" else "config"
            self.interface = None if self.mode != "config-if" else self.interface
            self._record(line, facts)
            return Reply("")
        if words[0] == "interface" and len(words) == 2 and self.mode == "config":
            self.mode, self.interface = "config-if", words[1]
            self._record(line, facts)
            return Reply("")
        if self.mode == "config" and words[0] == "hostname" and len(words) == 2:
            device.running_config = re.sub(r"^hostname .*$", f"hostname {words[1]}", device.running_config, flags=re.M)
            device.hostname = words[1]
            self._record(line, facts)
            return Reply("")
        if self.mode == "config-if" and words[0] == "description" and len(words) > 1:
            self._edit_interface(
                lambda body: [x for x in body if not x.startswith(" description ")], f" description {line[12:]}"
            )
            self._record(line, facts)
            return Reply("")
        if self.mode == "config-if" and words in (("shutdown",), ("no", "shutdown")):
            state = " shutdown" if words == ("shutdown",) else " no shutdown"
            self._edit_interface(
                lambda body: [x for x in body if x.strip() not in ("shutdown", "no shutdown")], state, last=True
            )
            self._record(line, facts)
            return Reply("")
        if words in (("write", "memory"), ("copy", "running-config", "startup-config")) and self.mode == "config":
            self._record(line, facts)
            return Reply("% EXPERIMENTAL: save is simulated and not verified iBOS behaviour")
        return self._error(line, tokens, words)

    def _edit_interface(self, keep, add: str, last: bool = False) -> None:
        lines = self.device.running_config.splitlines()
        header = f"interface {self.interface}"
        if header not in lines:
            return
        start = lines.index(header) + 1
        end = start
        while end < len(lines) and lines[end].startswith(" "):
            end += 1
        body = keep(lines[start:end])
        body = [*body, add] if last else [add, *body]
        self.device.running_config = "\n".join(lines[:start] + body + lines[end:]) + "\n"

    def _record(self, command: str, facts: tuple[str, ...]) -> None:
        register = evidence.load()
        known = [register.facts[f] for f in dict.fromkeys(("PROMPT-MODES", *facts)) if f in register.facts]
        level = max((f.level for f in known), key=ORDER.__getitem__)
        self.trace.append(
            TraceEntry(
                command, tuple(f.id for f in known if f.id != "PROMPT-MODES"), level, any(f.assumed for f in known)
            )
        )
