FROM python:3-slim
LABEL org.opencontainers.image.source=https://github.com/nexy7574/spanner-v3
LABEL org.opencontainers.image.license=AGPL-3
WORKDIR /spanner

COPY requirements.txt /tmp
RUN pip install -Ur /tmp/requirements.txt

COPY ./spanner/ /spanner/

CMD ["python", "main.py"]
