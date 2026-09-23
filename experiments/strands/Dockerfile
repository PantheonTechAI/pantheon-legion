FROM python:3.12-slim@sha256:6c4dd321d176d61ea848dc8c73a4f7dbae8f70e0ee48bb411ea2f045b599fa8e
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 AWS_EC2_METADATA_DISABLED=true
WORKDIR /opt/legion
COPY experiments/strands/requirements.lock /opt/requirements.lock
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r /opt/requirements.lock
COPY experiments/strands/__init__.py experiments/strands/worker.py experiments/strands/model.py experiments/strands/protocol.py experiments/strands/telemetry.py /opt/legion/experiments/strands/
USER 65534:65534
ENTRYPOINT ["python", "-m", "experiments.strands.worker", "/run/legion/worker.sock"]
