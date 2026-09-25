# Code Review Desk

## Environment setup

The system default Python was **3.14.5**, which is outside the Python range
selected for Chainlit compatibility. This project therefore pins its
environment to **CPython 3.13.15** inside the project root.

From `05_Code_Review_Desk`, the reproducible setup commands are:

```powershell
uv venv --python 3.13 .venv
uv sync --python .venv
```

Activate it in PowerShell with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Dependencies are declared in `pyproject.toml` and installed only into this
`uv`-managed environment.
