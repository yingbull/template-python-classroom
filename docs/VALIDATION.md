# Validation

The template is derived from the existing course runtime, with checkout-specific
Compose identities, an explicit host bind mount, Auto Save, and a workspace
identity/mount check. It has no automatic local backup feature.

## Local validation — September 16, 2026

- All 34 helper tests passed with Python 3.13 inside the devcontainer and
  Python 3.14 on the Linux host. The sample assignment test also passed.
- Ruff lint and formatting checks passed.
- Dev Containers CLI 0.80.0 built and started the environment using rootless
  Podman 5.8.2 and podman-compose 1.5.0 through Docker CLI compatibility.
- The container smoke check confirmed non-root Python, a writable virtual
  environment, the workspace mount and identity, Continue configuration,
  Ollama 0.33.3 connectivity, and the tutor gateway health endpoint.
- An untracked file created inside `/workspace` appeared on the host. Removing
  this checkout's containers and recreating them produced a different container
  ID; the same file remained available both on the host and inside the new
  container. The temporary proof file was then removed.
- The existing course containers continued running throughout validation.
- The existing `classgh-setup.prepare_seed` function imported the public template
  with `--seed-dir .`. Its resulting Git tree matched the published source
  exactly, with one fresh commit, root-level Dev Containers configuration, and
  no generated host-specific files.

The lifecycle check exposed two Podman compatibility details: generated project
names use only letters and digits, and the generated configuration must be the
**first** Compose file. Some providers select the name from the first file before
merging subsequent files. The template and documented commands use this order.
Container creation also aligns `/opt/venv` ownership with the development user
after Dev Containers adjusts that user's UID to match the Linux host.

## CI coverage and limits

The [Template checks workflow](https://github.com/yingbull/template-python-classroom/actions/workflows/checks.yml)
tests Python helpers on Linux, macOS, and Windows; it exercises the actual Docker
devcontainer/persistence lifecycle on Linux. These are different levels of
validation: Python tests on Windows/macOS do not by themselves prove Docker
Desktop or Podman Desktop integration on those hosts. GPU overrides and AI model
quality are not part of these checks; validation does not download AI models.

No live students are invited during template validation. Deployment compatibility
is checked using the existing `classgh-setup` starter-export code; its full
organization provisioning still requires the instructor's organization, roster,
and administrative token scopes.
