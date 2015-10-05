#!/bin/bash
# Runs both unit tests as well as process integration tests

python3 env_expand.py
python3 env_parse.py
python3 events.py
python3 service_order.py
python3 syslog_spec.py

./run-el.sh
