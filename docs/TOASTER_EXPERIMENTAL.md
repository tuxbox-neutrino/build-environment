# Toaster Integration (Experimental)

Status: experimental.

This feature is available for local testing and future integration work, but it
is not part of the default, stable project workflow.

## Scope

- Intended for developers who want a web UI around BitBake builds.
- Current implementation uses helper targets in the top-level `Makefile`.
- Behavior and defaults may change.

## Commands

Initialize once (idempotent):

```bash
make init-toaster MACHINE=hd60 MACHINEBUILD=ax60
```

Start and stop:

```bash
make toaster-start TOASTER_WEBPORT=127.0.0.1:18083
make toaster-stop
```

## What `init-toaster` does

- Ensures build config exists (runs `make config` if needed).
- Creates a dedicated venv at `.tuxbox/toaster-venv`.
- Installs `poky/bitbake/toaster-requirements.txt`.
- On Python 3.13+, installs `legacy-cgi` in the venv.
- Initializes Toaster metadata via `toaster start noweb nobuild` and stops again.

## Important variables

- `TOASTER_WEBPORT`: bind address/port (default `localhost:8000`)
- `TOASTER_PYTHON`: Python executable for venv creation (default `python3`)
- `TOASTER_BUILD_DIR`: build dir used for `oe-init-build-env`
- `TOASTER_DIR`: Toaster data dir (default `.tuxbox/toaster`)
- `TOASTER_START_ARGS`: extra args forwarded to `toaster start`

## Common issue: Port already in use

Symptom:

- `CommandError: Port 8000 is already in use`

Resolution:

1. Use another port:
   `make toaster-start TOASTER_WEBPORT=127.0.0.1:18083`
2. Or free the existing service on `8000` before starting Toaster.

## Runtime files

- Session pid: `build/.toaster-session.pid`
- Session log: `build/toaster_session.log`
- Toaster runtime pids: `build/.toastermain.pid`, `build/.runbuilds.pid`

## Cleanup

Stop Toaster first:

```bash
make toaster-stop
```

Optional local cleanup:

```bash
rm -rf .tuxbox/toaster-venv .tuxbox/toaster
```
