ARG CLASSROOM_IMAGE=ghcr.io/yingbull/classroom-python:1.0.0@sha256:d119029807e318d6bf805b725591b83b06d731357e8e96ff18b98b400c517bc4
FROM ${CLASSROOM_IMAGE}

# Unchanged assignments use the packages already installed in the image.
# A customized requirements file still rebuilds a fresh virtual environment.
COPY requirements-dev.txt /tmp/course-requirements.txt
RUN if cmp -s /tmp/course-requirements.txt /usr/local/share/classroom/requirements-dev.txt; then \
        echo 'Using prebuilt classroom dependencies'; \
    else \
        /usr/local/bin/python -m venv --clear /opt/venv \
        && /opt/venv/bin/python -m pip install --no-cache-dir -r /tmp/course-requirements.txt \
        && chown -R vscode:vscode /opt/venv; \
    fi
