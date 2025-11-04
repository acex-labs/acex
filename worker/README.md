# ACE-X Worker

Distributed task execution engine for ACE-X automations.

## Installation

Basic installation:
```bash
pip install acex-worker
```

With Celery support:
```bash
pip install acex-worker[celery]
```

## Development

```bash
cd worker
poetry install --all-extras
```

## Usage

```python
from acex_worker import Worker

worker = Worker()
worker.start()
```

Or run as a standalone process:
```bash
acex-worker start
```

## Features

- Distributed task execution
- Queue management
- Task scheduling
- Worker pools
- Optional Celery integration

## Configuration

Create a `worker.yaml` configuration file:

```yaml
worker:
  concurrency: 4
  queue: default
  broker: redis://localhost:6379
```

## Documentation

See the [main documentation](../README.md) for more information.
