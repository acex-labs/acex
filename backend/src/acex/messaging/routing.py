from fnmatch import fnmatchcase

#: Job type pattern -> queue. One queue per flow; a job type that matches no
#: route cannot be published, since a queue nobody consumes would hold its
#: jobs forever without an error.
ROUTES: dict[str, str] = {
    "acex.ztp.*": "acex.ztp",
}

QUEUES: tuple[str, ...] = tuple(dict.fromkeys(ROUTES.values()))


class UnroutedJobType(LookupError):
    pass


def queue_for(job_type: str) -> str:
    for pattern, queue in ROUTES.items():
        if fnmatchcase(job_type, pattern):
            return queue
    raise UnroutedJobType(f"No queue is routed for job type {job_type!r}; add it to acex.messaging.ROUTES.")
