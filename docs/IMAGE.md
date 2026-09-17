# Published classroom image

The classroom tools are distributed as `ghcr.io/yingbull/classroom-python:1.0.0`.
The release includes native `linux/amd64` and `linux/arm64` images. Docker or
Podman selects the matching architecture automatically; Windows uses Linux
containers through WSL2 or its container engine's Linux VM.

Release 1.0.0 index digest:

```text
sha256:d119029807e318d6bf805b725591b83b06d731357e8e96ff18b98b400c517bc4
```

Both native builds and their tests passed in
[publication run 35256769500](https://github.com/yingbull/template-python-classroom/actions/runs/35256769500).
Anonymous access to both platform manifests was verified after publication.

The template pins the release's multi-platform manifest digest in
`.devcontainer/Dockerfile` and `.devcontainer/devcontainer.json`. Both references
must stay identical. No floating `latest` tag is used.

## What is included

- The Microsoft Python 3.13 Bookworm devcontainer base.
- The packages in `requirements-dev.txt`, preinstalled in `/opt/venv`.
- The same shell activation and non-root development-user setup as the original
  locally built environment.

Assignment files, student work, credentials, Ollama, AI model downloads, and
VS Code extension installations are not baked into this image. The host workspace
mount, per-checkout isolation, workspace checks, and companion Ollama service are
still configured by the template.

The initializer uses this same image to detect the host engine and write the
checkout-specific Compose configuration. The small assignment Dockerfile compares
its requirements with the list stored in the image. Matching requirements skip
pip entirely. Different requirements rebuild `/opt/venv` from scratch, preserving
the ability to add or remove dependencies for an assignment. This also avoids
retaining packages removed from the instructor's requirements list.

## Publishing a new version

1. Update `requirements-dev.txt` and/or `.devcontainer/Dockerfile.image`, then
   commit and push to the template repository's `main` branch.
2. Run the **Publish classroom image** workflow with a new version:

   ```sh
   gh workflow run publish-image.yml \
     --repo yingbull/template-python-classroom --ref main \
     -f version=1.0.1
   ```

3. The workflow builds on native AMD64 and ARM64 runners. Each image must pass
   package-version, non-root permission, dependency-consistency, classroom-helper,
   and sample-assignment checks before its architecture image is uploaded.
   Only after both architectures succeed does the workflow publish the combined
   version tag. It refuses to replace a version tag it can already find.
4. Inspect the completed release:

   ```sh
   docker buildx imagetools inspect ghcr.io/yingbull/classroom-python:1.0.1
   ```

5. Update the two image references to the new version and its **index digest**
   (the digest containing both architectures, not an individual architecture's
   digest). Commit, push, and wait for **Template checks** to pass. Those checks
   include anonymous image access, container startup, customized requirements,
   and uncommitted-work persistence through container removal/recreation.

The publisher is restricted to `yingbull/template-python-classroom` on `main`.
Copies seeded into student repositories cannot publish to the instructor's
registry. Publication uses the workflow's temporary `GITHUB_TOKEN` with package
write permission; no long-lived registry token is stored in the repository.
Build caches are separate for each architecture. Build-specific architecture tags
are staging references; distribute the tested version tag and pinned index digest.

## Public access

GitHub creates new container packages as private, even when the source repository
is public. The package owner must set the package visibility to **Public** in
[package settings](https://github.com/users/yingbull/packages/container/classroom-python/settings)
before student deployment. This is a one-time setting; subsequent versions belong
to the same package. Students then need no registry login or token.

References: [GitHub Container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
and [package visibility](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility).
