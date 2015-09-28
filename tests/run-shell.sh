#!/bin/bash

if [ "$1" == "" ]; then
  echo 'usage: run_shell.sh <relative-test-subdir-path>'
  exit
fi

export PATH=$PWD/bin:$PATH
export CHTEST_DOCKER_CMD="sdnotify-exec --noproxy --verbose --wait-stop docker run %{SOCKET_ARGS}"

test-driver --shell el-tests/$1
