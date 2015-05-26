FROM ubuntu:14.04

ADD setup-bin/* *.sh /setup-bin/
ADD apps/ /apps/
ADD chaperone/ /setup-bin/chaperone/
RUN /setup-bin/install.sh

ENTRYPOINT ["/usr/local/bin/chaperone", "--config", "apps/chaperone.d"]
