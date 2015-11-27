#!/bin/sh

PATH=$PATH:/apps/docker/current/bin

# docker rm -f -v madsensor
# docker run -d -t -i --privileged --name madsensor -d samnco/madsensor
docker run -d -t -i --privileged --name ubuntu -d armv7/armhf-ubuntu
# docker wait madsensor

