# Python Classroom Template

A reusable Python development environment for instructor demonstrations and
private student assignments. Works with VS Code Dev Containers on Linux,
macOS, and Windows with WSL2. Deploy it with
[yingbull/classgh-setup](https://github.com/yingbull/classgh-setup), or use GitHub's
**Use this template** button.

Your code lives in a normal folder on your computer. The container provides
Python and development tools. **Saved files, including untracked and uncommitted
files, survive container replacement.** Work inside the VS Code workspace,
`/workspace` in the container. Other container folders are disposable.

## Student setup

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
   Python, Pylance, Ruff, and Continue editor extensions separately.
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

## Optional local AI tutor

Python development does not require an AI account, API key, or model download.
Ollama starts as an isolated companion service, but no models download on startup.

To enable the included local tutor, use **Terminal: Run Task → Ollama: Download
missing models**. The supplied choices currently require approximately 17 GB
of model downloads; allow at least 35 GB free disk space and preferably 16 GB+
system RAM. CPU inference works but can be slow. Students with smaller machines
can use the Python environment without downloading models. Instructors can
reduce the model list in `.continue/config.yaml` before distributing a starter.

Open Continue and select **Classroom Local Python**, then **Tutor - Gemma 4 E4B**.
Tutor mode aims to explain concepts and provide hints while leaving meaningful
exercise work to the student. **Direct** entries permit complete solutions.
These are teaching preferences, not academic-integrity enforcement; model
responses can be wrong or ignore instructions. Review and test suggestions.

Useful tasks:

- **Ollama: Check models** — report which selected models are available.
- **Ollama: Warm up Gemma tutor** — load the tutor before class.
- **Continue: Apply course config** — reapply changed model settings.

Model downloads persist in `classroom-python_ollama-models`, shared by these
templates on the same engine to avoid repeated downloads. Student source code
is not stored in that volume. GPU overrides are optional; see [GPU.md](docs/GPU.md).

## Deploy with classgh-setup

Use a standalone organization where you are the sole owner and base permissions
are **No permission**, as required by `classgh-setup`. From that script's checkout:

```sh
python3 classgh_setup.py students.txt \
  --org YOUR-CLASS --assignment assignment1 \
  --source yingbull/template-python-classroom \
  --seed-dir . \
  --commit-message 'Start assignment1' --yes
```

**`--seed-dir .` is essential:** `.devcontainer`, `.vscode`, and the Python
configuration must be at the student repository's root. Accepting the script's
usual assignment-subdirectory default nests the environment where VS Code will
not discover it automatically.

The script creates private `EMAILPREFIX-assignment1` repositories with a fresh
initial commit. Its student-team/invitation handling is unchanged. The public
visibility of this template does not make student repositories public.
Repeat with `--assignment assignment2` and the same provisioning state directory.

For a customized assignment, create an instructor starter from this template,
edit `ASSIGNMENT.md`, add your examples/tests/dependencies, commit and push, then
pass that starter as `--source OWNER/REPO`. The starter can itself be private.
For demos, use **Use this template** or `gh repo create` to make a demo repository,
clone it onto the host, and open it using the same steps.

`classgh-setup` disables GitHub Actions on student repositories. That does not
affect local Dev Containers, pytest, Ruff, or the tutor. The included GitHub
workflow validates the template itself; this release does not enable automated
online grading or reviews in student repositories.

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
add `--volumes`: the model volume is shared with other assignment checkouts.

Before moving a checkout, stop/remove its containers with the two-file command.
Then move the host folder and reopen it. The initializer derives a new identity
from the new location; it never moves, deletes, or migrates student files.
Do not open the same checkout through two different path aliases simultaneously.

## Template development

See [VALIDATION.md](docs/VALIDATION.md) for tested platforms and limits.

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s .devcontainer/tests -v
python -m pytest tests
ruff check .
ruff format --check .
```

The container-side smoke check is `python .devcontainer/smoke.py`. Public CI
tests Python helpers on Linux, macOS, and Windows, and the actual Docker
devcontainer/persistence lifecycle on Linux. It does not download AI models.

Derived from the Python/Continue/Ollama environment in
[PROG1784F26/PROG1784-F26](https://github.com/PROG1784F26/PROG1784-F26).
This is a separate template repository; course files, experiments, and student
work are not copied into it.
