# syntax=docker/dockerfile:1

FROM python:3.10-slim

WORKDIR /bing

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY src/ .

CMD [ "python3", "app.py"]
