FROM ubuntu:14.04

ADD setup-bin/* *.sh /setup-bin/
ADD chaperone/ /setup-bin/chaperone/
ADD etc-chaperone/ /etc/chaperone/
RUN /setup-bin/install.sh

ENTRYPOINT ["/usr/local/bin/chaperone"]
