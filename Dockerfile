FROM python:3.12-slim

EXPOSE 1237
LABEL org.opencontainers.image.source=https://github.com/nexy7574/spanner-v3
LABEL org.opencontainers.image.url=https://github.com/nexy7574/spanner-v3
LABEL org.opencontainers.image.license=AGPL-3
LABEL org.opencontainers.image.title="Spanner v3"
LABEL org.opencontainers.image.description="Version 3 of the spanner discord utility bot."

WORKDIR /spanner

RUN apt-get update && apt-get install -y git

COPY requirements.txt /tmp
RUN pip install -r /tmp/requirements.txt

COPY ./spanner/ /spanner/
COPY .git/ /.git/
# ^ actions/checkout does a treeless-copy of .git anyway.
RUN python _generate_version_info.py

CMD ["python", "main.py"]
