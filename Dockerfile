FROM python:3.12

WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt --src=/pip-repos

COPY . /app

EXPOSE 8000

ENV PATH="/app/scripts/bin:${PATH}"

CMD ["django-gunicorn"]
