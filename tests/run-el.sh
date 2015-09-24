#!/bin/bash

function relpath() { python -c "import os,sys;print(os.path.relpath(*(sys.argv[1:])))" "$@"; }

export PATH=$PWD/bin:$PATH

if [ "$1" == '-n' ]; then
  counter=$2
  shift 2
  for (( i=1; $i<=$counter; i++ )); do
    export CHTEST_LOGDIR=$PWD/test_logs/n$i
    $0 $* &
  done
  wait
  exit
fi

if [ "$1" != "" ]; then
  export CHTEST_ONLY_ENDSWITH=$1
fi

#export CHTEST_DOCKER_CMD="$PWD/bin/sdnotify-exec docker run %{SOCKET_ARGS}"

test-driver el-tests/basic-1
test-driver el-tests/simple-1
test-driver el-tests/simple-2
test-driver el-tests/cron-1
test-driver el-tests/fork-1
test-driver el-tests/inetd-1
test-driver el-tests/notify-1
