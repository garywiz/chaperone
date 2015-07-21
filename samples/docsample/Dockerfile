FROM ubuntu:14.04
MAINTAINER garyw@blueseastech.com

RUN apt-get update && \
    apt-get install -y openssh-server apache2 python3-pip && \
    pip3 install chaperone
RUN mkdir -p /var/lock/apache2 /var/run/apache2 /var/run/sshd /etc/chaperone.d

COPY chaperone.conf /etc/chaperone.d/chaperone.conf

EXPOSE 22 80

ENTRYPOINT ["/usr/local/bin/chaperone"]
