# Python Classroom Template

A reusable Python development environment for instructor demonstrations and
private student assignments. Works with VS Code Dev Containers on Linux,
macOS, and Windows with WSL2. Create a repository using GitHub's
**Use this template** button.

Your code lives in a normal folder on your computer. The container provides
Python and development tools. **Saved files, including untracked and uncommitted
files, survive container replacement.** Work inside the VS Code workspace,
`/workspace` in the container. Other container folders are disposable.

## Student setup

**Docker is the default.** Podman works with the unchanged repository when a
working Docker-compatible CLI and Compose are configured to use its engine.
Follow [Podman with no repository changes](.devcontainer/CONTAINER_ENGINE.md#podman-with-no-repository-changes)
for platform setup and the two checks to run before `code .`. Installing Podman
alone does not provide that compatibility setup. The guide also documents
explicitly selecting the `podman` executable as an alternative.

1. Install **Git**, **VS Code**, and a container engine:
   - Linux: Docker Engine + Compose v2, or Podman with Docker CLI compatibility.
   - macOS: Docker Desktop or Podman Desktop with its machine running.
   - Windows: Docker Desktop with WSL2 integration, or Podman Desktop with Docker
     CLI compatibility. Use Linux containers. The Docker Desktop + WSL route is
     the recommended classroom baseline on Windows.
2. Install VS Code's **Dev Containers** extension
   (`ms-vscode-remote.remote-containers`). On Windows, also install **WSL**
   (`ms-vscode-remote.remote-wsl`) and open the checkout through WSL.
3. **In a host terminal**, clone the repository your instructor gives you:

   ```sh
   git clone https://github.com/YOUR-CLASS/YOUR-ASSIGNMENT.git
   cd YOUR-ASSIGNMENT
   code .
   ```

   Any folder name works. Linux/macOS: use a folder such as `~/courses/`.
   Windows: clone into your WSL Linux home, such as `~/courses/`, for better
   filesystem performance. On macOS, allow the engine to share that folder.
4. Run **Dev Containers: Reopen in Container** from the command palette.
   Open the repository root containing `.devcontainer`, not its parent folder.
5. The first build downloads the prepared classroom image with Python 3.13,
   pytest, Ruff, PyYAML, and jsonschema. VS Code installs the debugger and the
   Python, Pylance, and Ruff editor extensions separately.
6. In the **container terminal**, try:

   ```sh
   python examples/hello.py
   python -m pytest tests
   ruff check .
   ```

Press **F5** to debug the current Python file. VS Code's **Terminal: Run Task**
menu also contains Run, Test, Format, and workspace-check commands.

The classroom image is published for both Intel/AMD (`linux/amd64`) and ARM
(`linux/arm64`, including Apple Silicon using Linux containers). Unchanged
assignments reuse its installed Python packages without running pip. Editing
`requirements-dev.txt` and rebuilding still installs the assignment's requested
dependencies in a fresh virtual environment. The first download is still
required; later assignments can reuse cached image layers on the same engine.
See [Classroom image](docs/IMAGE.md) for publishing and version updates.

Official setup references: [VS Code Dev Containers](https://code.visualstudio.com/docs/devcontainers/containers),
[Docker WSL recommendations](https://docs.docker.com/desktop/features/wsl/best-practices/),
and [Podman Docker compatibility](https://podman-desktop.io/docs/migrating-from-docker/managing-docker-compatibility).

## Keeping your work

- Source files are **bind-mounted from the host checkout** to `/workspace`.
  Saving a file in that folder saves it on your computer, even before Git commit.
- Auto Save writes named files after a one-second delay. Give new untitled files
  a filename inside the workspace. Auto Save does not create commits or push.
- Startup and attachment checks print the host folder and show uncommitted work.
  A mismatched checkout identity or missing workspace mount produces an error.
- Each checkout gets its own container project name derived from its host path,
  so two assignments or two clones with the same folder name do not reuse the
  same development container. Generated machine-specific files are Git-ignored.
- Git history and project files stay on the host. Python packages installed only
  inside the container are disposable: add lasting dependencies to
  `requirements-dev.txt` and rebuild.
- Make small commits and push regularly. Use your computer's normal backup
  system for protection from accidental deletion or device failure. This
  template does not create local backup archives or automatic commits.

Only `/workspace` is mounted. **Do not clone a second assignment into `/workspaces`,
`/home/vscode`, or `/tmp` inside this container.** Clone it on the host and open
that checkout in its own VS Code window instead. Avoid **Clone Repository in
Container Volume** for this classroom pattern: it stores code in engine-managed
storage instead of the visible host folder.

A bind mount is not a backup: deleting a file through the container also deletes
the host file. WSL source folders survive container rebuilds, but removing the
WSL distribution removes those folders. See [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/).

## Stopping, rebuilding, and moving a checkout

Closing VS Code stops this checkout's services. Reopen the same host folder to
continue. Use **Dev Containers: Rebuild Container** after changing dependencies
or container settings; saved workspace files remain on the host.

For manual Compose commands, include both configuration files in this order.
The generated file comes first because some Podman Compose versions choose the
project name before merging later files. After a
successful initial setup, from the **host checkout**:

```sh
docker compose -f .devcontainer/compose.runtime.yaml -f .devcontainer/compose.yaml stop
```

Do not use a bare `docker compose` in `.devcontainer`: the generated override
contains this checkout's project identity and engine-specific permissions.
To remove only this checkout's containers, replace `stop` with `down`. Do not
add `--volumes`: shared service data is used by other assignment checkouts.

Before moving a checkout, stop/remove its containers with the two-file command.
Then move the host folder and reopen it. The initializer derives a new identity
from the new location; it never moves, deletes, or migrates student files.
Do not open the same checkout through two different path aliases simultaneously.

## Template development

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s .devcontainer/tests -v
python -m pytest tests
ruff check .
ruff format --check .
```

The container-side smoke check is `python .devcontainer/smoke.py`. The
[Template checks workflow](https://github.com/yingbull/template-python-classroom/actions/workflows/checks.yml)
tests Python helpers on Linux, macOS, and Windows, and the actual Docker
devcontainer/persistence lifecycle on Linux. Local Linux checks also passed
with Podman through both Docker CLI compatibility and explicit Podman selection.
Desktop integration on macOS/Windows has not been exercised by these checks.

Derived from the Python development environment in
[PROG1784F26/PROG1784-F26](https://github.com/PROG1784F26/PROG1784-F26).
This is a separate template repository; course files, experiments, and student
work are not copied into it.
