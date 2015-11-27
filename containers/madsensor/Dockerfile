FROM armv7/armhf-ubuntu

RUN apt-get update && apt-get upgrade -yqq

RUN \
  apt-get install -y build-essential && \
  apt-get install -y curl git htop man unzip wget nano

# bluez dependencies
RUN \
  apt-get install -y libglib2.0-dev libical-dev libreadline-dev libudev-dev libdbus-1-dev libdbus-glib-1-dev

# debugging
RUN \
  apt-get install -y usbutils strace

# bluez itself
RUN apt-get install -yqq python bluetooth bluez rfkill libbluetooth-dev

# Enable systemd
ENV INITSYSTEM on

# Testing some hack I found in https://github.com/ianblenke/docker-avahi
RUN mkdir -p /var/run/dbus
VOLUME /var/run/dbus

CMD ["bash"]


