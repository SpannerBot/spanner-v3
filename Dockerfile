FROM python:3-alpine

WORKDIR /spanner

COPY requirements.txt /tmp
RUN pip install -Ur /tmp/requirements.txt

COPY ./spanner/ /spanner/

CMD ["python", "main.py"]
