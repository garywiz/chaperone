FROM ubuntu:14.04

ADD setup-bin/* *.sh /setup-bin/
ADD apps/ /apps/
ADD chaperone/ /setup-bin/chaperone/
RUN /setup-bin/install.sh

# We use the environment variable instead of entrypoint args so that any default can be overridden by CMD
ENV CHAPERONE_OPTIONS --config apps/chaperone.d

ENTRYPOINT ["/usr/local/bin/chaperone"]
