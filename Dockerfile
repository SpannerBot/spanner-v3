FROM python:3-alpine

EXPOSE 1237
LABEL org.opencontainers.image.source=https://github.com/nexy7574/spanner-v3
LABEL org.opencontainers.image.url=https://github.com/nexy7574/spanner-v3
LABEL org.opencontainers.image.license=AGPL-3
LABEL org.opencontainers.image.title="Spanner v3"
LABEL org.opencontainers.image.description="Version 3 of the spanner discord utility bot."

WORKDIR /spanner

COPY requirements.txt /tmp
RUN pip install -U pip wheel setuptools
RUN pip install -Ur /tmp/requirements.txt

COPY ./spanner/ /spanner/

CMD ["python", "main.py"]
