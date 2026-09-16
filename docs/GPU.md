# Optional GPU support

The default template uses CPU inference; no GPU is required for Python or tests.
GPU use requires a supported host, drivers, and engine setup. The template does
not install host GPU drivers. macOS container inference uses CPU; Apple GPU
passthrough is not available through this Linux-container configuration.

After configuring your host, append one suitable file to `dockerComposeFile` in
`.devcontainer/devcontainer.json`, after both `compose.runtime.yaml` and
`compose.yaml`:

| Host/engine | Optional file |
| --- | --- |
| Docker with NVIDIA Container Toolkit | `compose.nvidia.yaml` |
| Podman with NVIDIA CDI configured | `compose.nvidia-cdi.yaml` |
| Supported Linux AMD ROCm host | `compose.rocm.yaml` |
| Linux AMD/Intel with accessible `/dev/dri` | `compose.vulkan.yaml` |

Podman users whose GPU requires supplementary host groups may also need
`compose.podman-groups.yaml` with the `crun` runtime. If SELinux blocks GPU
device access, `compose.gpu-selinux.yaml` limits the label exception to Ollama.
These two files are specialist options, not default configuration.

Rebuild the container after changes. Include every chosen override after the
two base files when issuing manual Compose commands. Model outputs and hardware
performance are not validated by the template's ordinary CI.
