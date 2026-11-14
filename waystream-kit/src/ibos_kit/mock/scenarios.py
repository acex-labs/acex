from dataclasses import dataclass, field, replace

CREDENTIALS = {"username": "lab", "password": "lab-password-not-secret", "enable": "lab-enable-not-secret"}

RUNCFG_ASR = (
    "ADMIN-LEVEL-COMMANDS",
    "RUNCFG-COMMAND",
    "RUNCFG-HEADER",
    "RUNCFG-INDENT",
    "RUNCFG-ORDER",
    "RUNCFG-END-MARKER",
    "RUNCFG-BLOCK-SEPARATOR",
    "STANZA-SYNTAX",
    "INTERFACE-NAMES",
    "INTERFACE-NO-SHUTDOWN",
)
RUNCFG_MS4K = tuple("RUNCFG-ORDER-MS4K" if f == "RUNCFG-ORDER" else f for f in RUNCFG_ASR)


@dataclass(frozen=True)
class Command:
    words: tuple[str, ...]
    fixture: str | None = None
    privileged: bool = False
    facts: tuple[str, ...] = ()
    live_config: bool = False


@dataclass(frozen=True)
class Profile:
    key: str
    title: str
    model: str
    firmware: str
    hostname: str
    start_mode: str = "user"
    enable_password: str | None = None
    pager_command: bool = False
    assumptions: tuple[str, ...] = ()
    commands: tuple[Command, ...] = ()
    contexts: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Faults:
    latency_ms: int = 0
    hang_on: tuple[str, ...] = ()
    drop_after_lines: int | None = None
    reject_logins: bool = False
    legacy_kex_only: bool = False


@dataclass
class Device:
    profile: Profile
    faults: Faults = Faults()
    prompt_trailing_space: bool = False
    experimental_config_mode: bool = False
    running_config: str = ""
    hostname: str = ""

    def __post_init__(self):
        self.hostname = self.hostname or self.profile.hostname


def _show(words: str, fixture: str, facts: tuple[str, ...], privileged: bool = False) -> Command:
    return Command(tuple(words.split()), fixture=fixture, privileged=privileged, facts=facts)


def _running_config(fixture: str, facts: tuple[str, ...]) -> Command:
    return Command(("show", "running-config"), fixture=fixture, privileged=True, facts=facts, live_config=True)


def _context(fixture: str, facts: tuple[str, ...]) -> Command:
    return Command(
        ("show", "running-configuration", "context", "interface", "<interface>"),
        fixture=fixture,
        privileged=True,
        facts=facts + ("RUNCFG-CONTEXT", "ADMIN-LEVEL-COMMANDS"),
    )


CONTEXT_21 = "ms4000-6.3.5/show-running-configuration-context-interface-gigabitethernet21.txt"

PROFILES = {
    "a-asr6000-635": Profile(
        key="a-asr6000-635",
        title="ASR6000 on iBOS 6.3.5-ED-R, no clients connected",
        model="ASR6000",
        firmware="ibos-asr6k-6.3.5-ED-R",
        hostname="asr-lab-01",
        commands=(
            _show("show version", "asr6000-6.3.5/show-version.assumed.txt", ("SHOW-VERSION-ASR6000",)),
            _running_config("asr6000-6.3.5/running-config.txt", RUNCFG_ASR),
            _show(
                "show ip interface brief",
                "asr6000-6.3.5/show-ip-interface-brief.txt",
                ("SHOW-IP-INTERFACE-BRIEF", "COMMAND-ABBREVIATION"),
            ),
        ),
    ),
    "b-ms4000-635": Profile(
        key="b-ms4000-635",
        title="MS4000 on iBOS 6.3.5-ED-R, S-VLAN with UNI and NNI ports, no clients",
        model="MS4026-AC",
        firmware="ibos-ms4k-6.3.5-ED-R",
        hostname="ms-lab-01",
        commands=(
            _show("show version", "ms4000-6.3.5/show-version.assumed.txt", ("SHOW-VERSION-MS4K-635",)),
            _running_config("ms4000-6.3.5/running-config.txt", RUNCFG_MS4K),
            _show("show vlan", "ms4000-6.3.5/show-vlan.txt", ("SHOW-VLAN", "COMMAND-ABBREVIATION")),
            _context(CONTEXT_21, ()),
        ),
        contexts={"gigabitethernet21": CONTEXT_21},
    ),
    "c-ms4000-635-client": Profile(
        key="c-ms4000-635-client",
        title="MS4000 on iBOS 6.3.5-ED-R with a DHCP client: !volatile lines in the running configuration",
        model="MS4026-AC",
        firmware="ibos-ms4k-6.3.5-ED-R",
        hostname="ms-lab-01",
        commands=(
            _show("show version", "ms4000-6.3.5/show-version.assumed.txt", ("SHOW-VERSION-MS4K-635",)),
            _running_config("ms4000-6.3.5/running-config.with-client.txt", RUNCFG_MS4K + ("VOLATILE-LINES",)),
            _show("show vlan", "ms4000-6.3.5/show-vlan.txt", ("SHOW-VLAN", "COMMAND-ABBREVIATION")),
            _show("show clients", "ms4000-6.3.5/show-clients.txt", ("SHOW-CLIENTS",)),
            _context(CONTEXT_21, ("VOLATILE-LINES",)),
        ),
        contexts={"gigabitethernet21": CONTEXT_21},
    ),
    "d-ms4000-630": Profile(
        key="d-ms4000-630",
        title="MS4000 on iBOS 6.3.0-ED-R with an enable password; the commands of the installation guide",
        model="MS4026-AC",
        firmware="ibos-ms4k-6.3.0-ED-R",
        hostname="ms-lab-04",
        enable_password=CREDENTIALS["enable"],
        assumptions=("SSH-SERVER-FIRMWARE",),
        commands=(
            _show("show version", "ms4000-6.3.0/show-version.txt", ("SHOW-VERSION-MS4K-630",)),
            _show("show vlan", "ms4000-6.3.0/show-vlan.txt", ("SHOW-VLAN", "COMMAND-ABBREVIATION")),
            _show("show pfdp neighbours", "ms4000-6.3.0/show-pfdp-neighbours.txt", ("SHOW-PFDP-NEIGHBOURS",)),
            _running_config("ms4000-6.3.0/running-config.assumed.txt", RUNCFG_MS4K + ("RUNCFG-MS4K-630",)),
        ),
    ),
    "e-ms7048-762": Profile(
        key="e-ms7048-762",
        title="MS7048-AC on iBOS 7.6.2-GD-R, ethernetS/P ports: show running-config is refused until enable",
        model="MS7048-AC",
        firmware="ibos-cma-7.6.2-GD-R",
        hostname="ms-lab-05",
        pager_command=True,
        commands=(
            _show("show version", "ms7048-7.6.2/show-version.txt", ("SHOW-VERSION-7X",)),
            _running_config(
                "ms7048-7.6.2/running-config.assumed.txt",
                RUNCFG_MS4K + ("RUNCFG-7X-REJECTED", "RUNCFG-7X-AFTER-ENABLE"),
            ),
        ),
    ),
}
PROFILES["e-ms7048-762-never"] = replace(
    PROFILES["e-ms7048-762"],
    key="e-ms7048-762-never",
    title="Hypothetical fault: the MS7048-AC refuses show running-config even after enable",
    commands=tuple(c for c in PROFILES["e-ms7048-762"].commands if c.words != ("show", "running-config")),
)
PROFILES["f-failures"] = replace(
    PROFILES["b-ms4000-635"],
    key="f-failures",
    title="MS4000 on iBOS 6.3.5-ED-R with SSH and session faults switched on by the caller",
)

SCENARIOS = PROFILES
LETTERS = {"a": "a-asr6000-635", "b": "b-ms4000-635", "c": "c-ms4000-635-client", "d": "d-ms4000-630"}
LETTERS |= {"e": "e-ms7048-762", "f": "f-failures"}


def device_for(key: str, **overrides) -> Device:
    from ibos_kit.paths import DEVICE_FIXTURES

    profile = PROFILES[LETTERS.get(key, key)]
    fault_names = set(Faults.__dataclass_fields__)
    faults = Faults(**{k: v for k, v in overrides.items() if k in fault_names})
    others = {k: v for k, v in overrides.items() if k not in fault_names}
    if "start_mode" in others:
        profile = replace(profile, start_mode=others.pop("start_mode"))
    live = next((c for c in profile.commands if c.live_config), None)
    running = (DEVICE_FIXTURES / live.fixture).read_text() if live else ""
    return Device(profile=profile, faults=faults, running_config=running, **others)
