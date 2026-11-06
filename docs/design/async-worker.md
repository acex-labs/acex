# Async worker

Plan for rewriting the worker so that one process runs many I/O-bound jobs at once on a single event loop. Nothing
is implemented yet; this document is what the draft pull request is reviewed against.

## Why

Most jobs wait on devices (SSH, NETCONF) and on the acex API. How many jobs a worker runs at once should depend on
how many device sessions it can hold open, not on how many CPU cores it has.

Today:

- The worker is a Celery app with `worker_pool="threads"` and no concurrency set
  ([app.py](../../worker/src/acex_worker/app.py)). Celery then uses `billiard.cpu_count()`, which inside a container
  is the host's core count, not the container's CPU limit. A pod limited to 1 CPU on a 32-core node runs 32 threads.
- The driver layer is already async: Cisco IOS uses scrapli over asyncssh, and Junos runs netmiko through
  `asyncio.to_thread`. But each job calls `asyncio.run(...)` in its own Celery thread
  ([execute.py](../../worker/src/acex_worker/handlers/execute.py)), so every job gets an event loop of its own. The
  number of threads still sets the number of jobs that can run at once, so async gives us nothing yet.
- A run is one job per node, so the number of jobs running at once is the number of devices being worked on at once.

The worker itself contributes little to how fast jobs get done. We gain most by letting one process hold hundreds of
device sessions open while they wait.

## Worker runtime

One process, one event loop, no Celery.

- **Consumer (aio-pika).** `prefetch_count` is the worker's concurrency and the only limit on it: RabbitMQ never
  hands the worker more messages than it has free slots. Each message becomes an `asyncio.Task` that claims the job,
  runs its handler and reports how it ended. The message is acknowledged once the job has finished, as today, and
  the claim keeps a redelivery safe.
- **Graceful shutdown.** On SIGTERM the worker stops consuming, waits for running jobs up to a timeout, then closes
  the connection. The NED restart (a NED upgraded on disk after it was imported) takes the same path; today it relies
  on Celery's warm shutdown.
- **Blocking drivers.** Drivers that run blocking libraries through `to_thread` (Junos and netmiko) get a default
  executor sized to the worker's concurrency. Python's default executor caps out at `min(32, cpu + 4)` threads,
  which would otherwise become the real limit.
- **NED installs.** `pip install` runs in a thread, behind an `asyncio.Lock` so that two jobs never install into the
  same environment at once.
- **Settings.** A `WorkerSettings` (pydantic-settings) with `ACEX_WORKER_CONCURRENCY` (default 100) and the shutdown
  timeout, next to the existing `ACEX_*` variables.

### Layout

```
acex_worker/
  main.py       startup: auth, connect, sync NEDs, Worker.run()
  settings.py   WorkerSettings
  worker.py     class Worker: consumer, running tasks, shutdown
  runner.py     class JobRunner: claim → handler → succeed / fail
  neds.py       class NedStore: async load and install
  handlers/
    base.py         Handler, JobContext
    operations.py   NodeOperation, execute, ping
    ztp.py          discover, provision
  registry.py   job type → handler
```

`app.py` and `base_handler.py` go away.

## Handler contract

```python
class Handler[D: BaseModel, R: BaseModel | None](ABC):
    data: type[D]

    @abstractmethod
    async def handle(self, ctx: JobContext, data: D) -> R: ...
```

- `JobContext` holds the job, the API client and the `NedStore`.
- The runner validates the job's data against `data` before calling the handler. A handler that raises fails the
  job with the exception as its error, and the backend still checks the result against the job type. This replaces
  `handle_hook` and `HandlerResponse`.
- `NodeOperation` fetches the node and its credentials, opens a session and calls `operate(session, data)`, as
  today but async all the way down.

## Changes outside the worker

### Backend producer: plain AMQP instead of Celery

Once the worker no longer runs Celery, Celery's message protocol is a dependency we don't need. The backend publishes a
plain AMQP message instead:

| Field | Value |
|---|---|
| body | `{"job_id": 123}` (JSON) |
| `type` | the job type, e.g. `acex.operations.execute` |
| `message_id` | the job id |
| `delivery_mode` | persistent |

The rest of the contract stays the same: one durable classic queue per flow, declared the same way on both sides, and
the message carries only the job id. The change is confined to
[producer.py](../../backend/src/acex/messaging/producer.py), and Celery is removed as a dependency from both the
backend and the worker.

This changes the earlier decision to run jobs with Celery over RabbitMQ.

### Async API client

`acex_client` is synchronous only. Its resources are declarative (`@action` methods with `...` bodies that call
`RestClient.request`), so an `AsyncAcex` on an `AsyncRestClient` (httpx `AsyncClient`) should be able to share
the same resource definitions. The worker then makes all its API calls through one async connection pool.

This is the largest part of the work, and it touches a package that the CLI, the MCP server and the scripts also use.
The alternative is for the worker to call the synchronous client through `to_thread`. API calls take milliseconds,
so that works, but it is a stopgap.

### ZTP handlers

`HandleZtpDiscovery` and `HandleZtpProvision` call `driver.discover(...)` and `driver.provision(...)`, which no
longer exist on the drivers or in devkit. They are rewritten on the session API: `get_facts` for discover and
`apply` for provision.

`driver.session()` takes a node, but discover has only an IP address and the bootstrap login. Drivers need a way to
open a session to an address without a node. That is a driver interface question and is planned separately.

## Open points

- **RabbitMQ consumer timeout.** RabbitMQ closes a channel that holds an unacknowledged message longer than
  `consumer_timeout` (30 minutes by default). If the worker acknowledges only after the job ends, no job may run
  longer than that. If provisioning or long workflow steps can, the alternative is to acknowledge right after the
  claim and let the jobs table detect jobs that are stuck, which fits with the jobs table being the record of what
  has to run.
- **Default concurrency.** 100 is a starting point. The real ceiling is likely to be the acex API (each job claims,
  fetches the node and its credentials, and reports) and the devices' AAA and SSH limits, not the worker.

## Order of work

1. `AsyncAcex` in `acex_client`, sharing the resource definitions.
2. Plain AMQP publishing in the backend; Celery removed from the backend.
3. The worker: runtime, handler contract, operations handlers, NED store, settings. Celery removed from the worker.
4. ZTP handlers on the session API, once drivers can open a session to an address.

Steps 2 and 3 have to ship together, since they change the message format on both sides.
