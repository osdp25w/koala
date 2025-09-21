FROM python:3.10.13-slim

WORKDIR /usr/src/app

RUN pip install poetry==1.6.1

COPY pyproject.toml poetry.lock ./

RUN apt-get update && \
    apt-get install -y \
        vim unzip \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
        build-essential \
        && rm -rf /var/lib/apt/lists/*

# 設定 GDAL 環境變數
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

COPY requirements.txt requirements.txt

RUN poetry install

COPY export-requirements.sh ./

RUN chmod +x export-requirements.sh
