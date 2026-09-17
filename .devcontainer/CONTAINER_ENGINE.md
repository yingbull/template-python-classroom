# Docker default and switching to Podman

**Docker is the default.** Opening the cloned folder with `code .` does not
install or automatically select a container engine. VS Code Dev Containers
normally runs the `docker` executable, and this repository's startup hook also
explicitly runs `docker`. With a working Docker-compatible CLI connected to
Podman, the unchanged repository uses Podman. Installing Podman alone does not
provide that compatibility setup.

## Default: Docker

Install and start Docker Desktop on macOS/Windows, or Docker Engine and Compose
v2 on Linux. Use Linux containers. On Windows with a WSL-hosted checkout, enable
Docker Desktop integration for that WSL distribution.

In a **host terminal**, in the same environment from which you run `code .`:

```sh
docker info
docker compose version
```

Both commands must succeed. In VS Code's host **User** settings, leave
**Dev Containers: Docker Path** at its default `docker`. If you previously
selected Podman, reset that setting. Keep the first `initializeCommand` entry in
`.devcontainer/devcontainer.json` as `"docker"`.

Then run **Dev Containers: Reopen in Container**. If VS Code asks to install
Docker despite it being installed, check that its CLI is on the host's PATH,
start the engine, and restart VS Code after installation. A client version alone
does not prove that the engine is running.

## Podman with no repository changes

**Yes: once the `docker` command is connected to Podman and Compose works, just
open the clone with `code .` and reopen in the container.** Leave VS Code's
**Dev Containers: Docker Path** set to `docker`, and leave `initializeCommand`
unchanged. You do not need a Docker daemon or Docker Desktop for this route.

This is a one-time setup on the student's computer. The compatibility layer
routes the `docker` command to Podman; the repository does not guess which engine
to use when both are installed.

### Linux

Use your distribution's Podman 5+ packages, Docker CLI compatibility package,
and Compose provider. Common package commands are:

```sh
# Fedora
sudo dnf install podman podman-docker podman-compose

# Debian/Ubuntu, where the distribution provides Podman 5 or newer
sudo apt install podman podman-docker podman-compose
```

Choose the command for your distribution. See [Podman installation](https://podman.io/docs/installation)
if its repositories supply an older release. `podman-docker` provides the real
`docker` executable that launches Podman; a shell alias is not a substitute.
If Docker is already installed, choose which implementation should supply that
command instead of installing conflicting CLI packages blindly.

### Podman Desktop on macOS or Windows

1. Install [Podman Desktop](https://podman-desktop.io/docs/installation), finish
   Podman onboarding, and create/start its Linux machine.
2. Open **Settings → Resources → Compose → Setup** and follow the prompts.
   This installs a Compose provider. See [Compose setup](https://podman-desktop.io/docs/compose/setting-up-compose).
3. Open **Settings → Docker Compatibility**. Select the Podman connection under
   **Docker CLI Context** and check that the socket is reachable. On macOS,
   enable **Third-Party Docker Tool Compatibility** if needed. The
   [platform-specific compatibility guide](https://podman-desktop.io/docs/migrating-from-docker/managing-docker-compatibility)
   shows these controls; Windows does not have the macOS-only toggle.
4. Make sure a real `docker` CLI is installed and on PATH. Socket compatibility
   alone does not install it. Run the verification below; if either command is
   missing, use the missing-CLI instructions that follow.

### Verify, then open the course

In the **host terminal**, in the same Windows/WSL/macOS/Linux environment that
will launch VS Code, run:

```sh
docker info
docker compose version
```

Both must succeed, and `docker info` must reach the intended Podman engine.
With Linux `podman-docker`, the Podman compatibility notice is normal. With a
Docker client using Podman's API, inspect the server information and selected
Podman context. Merely seeing a client version is not enough.

Then, from the cloned repository folder:

```sh
code .
```

Run **Dev Containers: Reopen in Container**. No repository configuration edits
are required. If VS Code was already open during installation, close all VS Code
windows and reopen it so it sees the updated PATH and engine configuration.

If Windows VS Code is connected to WSL, perform the CLI checks inside that WSL
distribution. A working Windows CLI is not automatically a working WSL CLI;
follow [Podman access from another WSL distribution](https://podman-desktop.io/docs/podman/accessing-podman-from-another-wsl-instance)
when using the Windows Podman machine from WSL.

### If Podman Desktop did not install the `docker` command

These install client tools only; keep Podman as the running engine.

**macOS with Homebrew:**

```sh
brew install docker docker-compose
```

If `docker-compose version` works but `docker compose version` does not, follow
[Homebrew's Compose plugin setup](https://formulae.brew.sh/formula/docker-compose).
It explains adding Homebrew's `lib/docker/cli-plugins` directory to
`cliPluginsExtraDirs` in `~/.docker/config.json`. Merge the entry into the existing
file; use the actual prefix printed by `brew --prefix`.

**Windows PowerShell (Windows-hosted VS Code):**

```powershell
winget install --id Docker.DockerCLI --exact
```

Reopen PowerShell afterward. Run Podman Desktop's Compose setup above if
`docker-compose version` is missing. If the standalone command works but
`docker compose version` is missing, make that installed executable available as
[a Docker CLI plugin](https://github.com/docker/cli/blob/master/cli-plugins/manager/manager.go):

```powershell
$classroomCompose = (Get-Command docker-compose -ErrorAction Stop).Source
$classroomPlugins = Join-Path $env:USERPROFILE '.docker\cli-plugins'
New-Item -ItemType Directory -Force -Path $classroomPlugins | Out-Null
Copy-Item $classroomCompose (Join-Path $classroomPlugins 'docker-compose.exe')
docker compose version
```

This uses Docker's default user configuration folder. If you explicitly set
`DOCKER_CONFIG`, use its `cli-plugins` directory instead. Repeat the copy after
updating the standalone Compose executable. The Windows CLI package is available
through [Microsoft's WinGet catalog](https://github.com/microsoft/winget-pkgs/tree/master/manifests/d/Docker/DockerCLI).

If the CLI exists but connects to the wrong engine, choose the Podman context in
Podman Desktop, or follow its [Docker context / DOCKER_HOST instructions](https://podman-desktop.io/docs/migrating-from-docker/using-the-docker_host-environment-variable).
Those instructions obtain the actual socket/pipe from `podman machine inspect`;
do not copy a socket path from someone else's machine. An existing `DOCKER_HOST`
or `DOCKER_CONTEXT` environment variable can override the selected connection.

## Alternative: select Podman explicitly

You do not need Docker Desktop or a Docker daemon for this route.

1. Install Podman **5 or newer** and a Compose provider. With Podman Desktop,
   complete its [Compose setup](https://podman-desktop.io/docs/compose/setting-up-compose).
   On macOS/Windows, create and start the Podman machine. On Linux, a native
   Podman installation can run without a VM; `podman-compose` is one provider.
2. Check the CLI from the **host terminal** that launches VS Code:

   ```sh
   podman info
   podman compose version
   ```

   Both must succeed. Windows installations are not automatically available
   inside WSL: if the VS Code folder is opened through WSL, configure and check
   Podman access from that same distribution. The engine must be able to mount
   the host checkout.
3. In the VS Code window opened on the **host folder**, open Settings and search
   for **Dev Containers: Docker Path**. Set it to `podman` in **User** settings
   (or the appropriate WSL/Remote settings). The JSON setting is:

   ```json
   "dev.containers.dockerPath": "podman"
   ```

   Merge this setting into the existing settings object. It belongs to the host
   VS Code configuration, not `customizations.vscode.settings` inside
   `devcontainer.json`, which configures the editor after container startup.
   If you previously set **Dev Containers: Docker Compose Path** to a
   Docker-only executable, reset it to its default so Dev Containers can use
   the selected CLI's `podman compose` command.
4. Open `.devcontainer/devcontainer.json` in your checkout. In the
   `initializeCommand` array, change **only the first entry** from `"docker"`
   to `"podman"`. Leave the image, mount, script, and other arguments unchanged.

   **Both steps 3 and 4 are required:** the VS Code setting selects the engine
   for Dev Containers, while the first startup-hook entry selects the engine
   for the runtime probe. Changing only one can still request Docker or use
   different engines for the probe and the workspace.
5. Run **Developer: Reload Window**, then **Dev Containers: Reopen in Container**
   (or **Rebuild Container** for a previously opened checkout).

This is a local engine preference; keep the startup-hook edit out of assignment
commits unless the instructor wants Podman to be the shared default. For manual
commands in the README, use `podman` wherever the executable is `docker`,
including `podman compose`. Preserve the documented Compose file order.

## Switching back or using computers with both engines

Before switching, stop this checkout's containers using its current engine.
To return to Docker, reset the VS Code Docker Path to `docker`, change the first
startup-hook entry back to `"docker"`, start Docker, reload the window, and
rebuild the container. Use `docker info` or `podman info` to verify the intended
engine; do not rely on whichever Desktop application happens to be open.

Each engine has its own image cache and model volumes, so a switch may download
them again. Saved coursework stays in the host checkout. Do not delete volumes
as part of switching. The runtime probe automatically adjusts permissions for
the engine **after it has been selected**; it does not select the host CLI.

Reference: [VS Code's Podman configuration](https://code.visualstudio.com/remote/advancedcontainers/docker-options#_podman).

See [Template development](../docs/template/README.md#template-development) for verification
coverage and platform limits.
