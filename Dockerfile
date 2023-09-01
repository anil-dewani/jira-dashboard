###########
# BUILDER #
###########

FROM python:3.9.6-alpine as builder


WORKDIR /usr/src/app

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

RUN apk update \
    && apk add gcc python3-dev musl-dev

RUN pip install --upgrade pip
COPY ./requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt

#########
# FINAL #
#########

FROM python:3.9.6-alpine

ARG APP_HOME=/app
RUN mkdir -p ${APP_HOME}
WORKDIR $APP_HOME

RUN addgroup -S app && adduser -S app -G app

RUN apk update
COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --no-cache /wheels/*

COPY . ${APP_HOME}

RUN chown -R app:app $APP_HOME

USER app
EXPOSE 10002
ENTRYPOINT [ "gunicorn", "--bind=0.0.0.0:10002", "app:app" ]
