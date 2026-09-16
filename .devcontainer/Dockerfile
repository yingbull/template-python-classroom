FROM mcr.microsoft.com/devcontainers/python:1-3.13-bookworm

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
COPY requirements-dev.txt /tmp/course-requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir -r /tmp/course-requirements.txt \
    && chown -R vscode:vscode /opt/venv \
    && echo '. /opt/venv/bin/activate' >> /home/vscode/.bashrc
