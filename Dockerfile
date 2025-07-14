FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN cp /etc/apt/sources.list /etc/apt/sources.list.bak && \
    echo "deb http://mirrors.aliyun.com/ubuntu/ noble main restricted universe multiverse" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/ubuntu/ noble-security main restricted universe multiverse" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/ubuntu/ noble-updates main restricted universe multiverse" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/ubuntu/ noble-backports main restricted universe multiverse" >> /etc/apt/sources.list \
    && apt update \
    && apt upgrade -y \
    && apt-get install -y python3 python3-pip \
    && apt clean && rm -rf /var/lib/apt/lists/*

RUN rm /usr/lib/python3.12/EXTERNALLY-MANAGED \
    && pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip install rich openai pydantic pyyaml httpx aiofiles gymnasium html2text numpy tenacity pillow uvicorn \
    && pip install playwright browsergym-core
RUN playwright install chromium
RUN playwright install-deps chromium