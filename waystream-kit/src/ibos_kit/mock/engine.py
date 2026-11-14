import re
import zlib
from dataclasses import dataclass

from ibos_kit import evidence
from ibos_kit.mock.scenarios import Command, Device
from ibos_kit.paths import DEVICE_FIXTURES

ALIASES = {"sh": "show", "int": "interface", "br": "brief"}
ERROR_PREFIX = "%-ERR: "
EXPERIMENTAL_BANNER = (
    "% EXPERIMENTAL PROFILE: configuration mode follows the MS 7000 7.5.2 command reference "
    "and has not been tried on a device; error answers are assumed."
)
ORDER = {"VERIFIED": 0, "INFERRED": 1, "UNKNOWN": 2}
INTERFACE_KINDS = (
    ("tengigabitethernet", "te"),
    ("gigabitethernet", "ge"),
    ("loopback", "lo"),
    ("downstream", "downstream"),
    ("vlan", "vlan"),
    ("ethernet", "eth"),
    ("tunnel", "tun"),
)

SPECIALS = (
    Command(("enable",), facts=("ENABLE-COMMAND",)),
    Command(("exit",)),
    Command(("terminal", "width", "<number>"), facts=("TERMINAL-COMMANDS",)),
    Command(("terminal", "lines", "<number>"), facts=("TERMINAL-COMMANDS",)),
)
PAGER = (
    Command(("terminal", "no", "pager"), facts=("TERMINAL-COMMANDS", "PAGER-BEHAVIOUR")),
    Command(("terminal", "pager"), facts=("TERMINAL-COMMANDS", "PAGER-BEHAVIOUR")),
)
CONFIG_ENTRY = Command(("configure", "terminal"), privileged=True, facts=("CONFIG-MODE-ENTRY",))
WRITE = (
    Command(("write",), privileged=True, facts=("CONFIG-SAVE-COMMIT",)),
    Command(("write", "memory"), privileged=True, facts=("CONFIG-SAVE-COMMIT",)),
)
HOSTNAME = re.compile(r"[A-Za-z0-9-]{1,63}")


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
        context = {"user": ">", "privileged": "#", "config": "(config)#"}.get(self.mode)
        if context is None:
            kind = next((k for prefix, k in INTERFACE_KINDS if (self.interface or "").startswith(prefix)), None)
            context = f"(config-if-{kind})#" if kind else "(config-if)#"
        return f"{self.device.hostname}{context}{' ' if self.device.prompt_trailing_space else ''}"

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

    def _commands(self, privileged: bool | None = None) -> list[Command]:
        privileged = self.mode == "privileged" if privileged is None else privileged
        commands = [c for c in self.device.profile.commands if privileged or not c.privileged]
        if self.device.profile.pager_command:
            commands += PAGER
        if self.device.experimental_config_mode and privileged:
            commands += [CONFIG_ENTRY, *WRITE]
        return [*commands, *SPECIALS]

    def _fits(self, pattern: str, word: str) -> bool:
        if pattern == "<interface>":
            return word in self.device.profile.contexts
        if pattern == "<number>":
            return word.isdigit() and 1 <= int(word) <= 65535
        return pattern == word

    def _match(self, words: tuple[str, ...], privileged: bool | None = None) -> Command | None:
        for command in self._commands(privileged):
            if len(command.words) == len(words) and all(
                self._fits(c, w) for c, w in zip(command.words, words, strict=True)
            ):
                return command
        return None

    def _error(
        self, line: str, tokens: list[tuple[str, int]], words: tuple[str, ...], privileged: bool | None = None
    ) -> Reply:
        commands = self._commands(privileged)
        position = next(
            (
                i
                for i in range(len(words))
                if not any(
                    len(c.words) > i and all(self._fits(c.words[j], words[j]) for j in range(i + 1)) for c in commands
                )
            ),
            len(tokens) - 1,
        )
        cause = ("TERMINAL-COMMANDS",) if words[:1] == ("terminal",) and position >= 1 else ()
        return self._error_at(line, tokens, position, cause)

    def _error_at(self, line: str, tokens: list[tuple[str, int]], position: int, cause: tuple[str, ...] = ()) -> Reply:
        word, start = tokens[position]
        self._record(line, (*cause, "ERROR-FORMAT"))
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
        if command.words[0] == "write":
            return Reply(self._write())
        text = self.device.running_config if command.live_config else (DEVICE_FIXTURES / command.fixture).read_text()
        text = text.rstrip("\n")
        limit = self.device.faults.drop_after_lines
        if command.live_config and limit is not None:
            return Reply("\n".join(text.splitlines()[:limit]), drop=True, prompt_follows=False)
        return Reply(text)

    def _write(self) -> str:
        config = self.device.running_config.encode()
        return f"Wrote {len(zlib.compress(config))} bytes compressed configuration ({len(config)} bytes uncompressed)"

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
        device = self.device
        if words[0] == "do" and len(words) > 1:
            command = self._match(words[1:], privileged=True)
            if command is None or command.words[0] in ("enable", "exit", "configure"):
                return self._error(line, tokens[1:], words[1:], privileged=True)
            return self._run(command, words[1:], ("CONFIG-MODE-ENTRY",))
        if words in (("end",), ("exit",)):
            self.mode = "privileged" if words == ("end",) or self.mode == "config" else "config"
            self.interface = None if self.mode != "config-if" else self.interface
            self._record(line, ("CONFIG-MODE-ENTRY",))
            return Reply("")
        if words[0] == "interface" and len(words) == 2 and self.mode == "config":
            self.mode, self.interface = "config-if", words[1]
            self._record(line, ("CONFIG-MODE-ENTRY",))
            return Reply("")
        if self.mode == "config" and words[0] == "hostname" and len(words) == 2:
            if not HOSTNAME.fullmatch(words[1]):
                return self._error_at(line, tokens, 1, ("HOSTNAME-RULES",))
            device.running_config = re.sub(r"^hostname .*$", f"hostname {words[1]}", device.running_config, flags=re.M)
            device.hostname = words[1]
            self._record(line, ("CONFIG-MODE-ENTRY",))
            return Reply("")
        if self.mode == "config-if" and words[0] == "description" and len(words) > 1:
            self._edit_interface(
                lambda body: [x for x in body if not x.startswith(" description ")], f" description {line[12:]}"
            )
            self._record(line, ("CONFIG-MODE-ENTRY",))
            return Reply("")
        if self.mode == "config-if" and words in (("shutdown",), ("no", "shutdown")):
            self._edit_interface(
                lambda lines: [x for x in lines if x.strip() != "no shutdown"],
                None if words == ("shutdown",) else " no shutdown",
                last=True,
            )
            self._record(line, ("INTERFACE-NO-SHUTDOWN",))
            return Reply("")
        return self._error(line, tokens, words)

    def _edit_interface(self, keep, add: str | None, last: bool = False) -> None:
        lines = self.device.running_config.splitlines()
        header = f"interface {self.interface}"
        if header not in lines:
            return
        start = lines.index(header) + 1
        end = start
        while end < len(lines) and lines[end].startswith(" "):
            end += 1
        body = keep(lines[start:end])
        if add is not None:
            body = [*body, add] if last else [add, *body]
        self.device.running_config = "\n".join(lines[:start] + body + lines[end:]) + "\n"

    def _record(self, command: str, facts: tuple[str, ...]) -> None:
        register = evidence.load()
        ids = dict.fromkeys(("PROMPT-MODES", *facts, *self.device.profile.assumptions))
        known = [register.facts[f] for f in ids if f in register.facts]
        level = max((f.level for f in known), key=ORDER.__getitem__)
        self.trace.append(
            TraceEntry(
                command, tuple(f.id for f in known if f.id != "PROMPT-MODES"), level, any(f.assumed for f in known)
            )
        )
