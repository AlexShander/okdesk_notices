FROM python:3.7-alpine

COPY . /var/app
WORKDIR /var/app
RUN pip3 install -r requirements.txt

ENTRYPOINT ["/bin/sh", "run_telegrm_snd.sh"]
