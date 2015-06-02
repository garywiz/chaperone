FROM chapdev/chaperone-base:latest

ADD *.sh /setup-bin/
ADD apps/ /apps/
RUN /setup-bin/install.sh

EXPOSE 8080
