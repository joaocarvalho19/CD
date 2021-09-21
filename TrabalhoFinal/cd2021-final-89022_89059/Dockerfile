FROM python:3.8-slim-buster

WORKDIR /

RUN pip install h11==0.12.0

COPY . /

CMD [ "python3", "-u", "slave.py"]
