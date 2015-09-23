#!/bin/bash

if [ "$1" == "" ]; then
  echo 'usage: run_shell.sh <relative-test-subdir-path>'
  exit
fi

export PATH=$PWD/bin:$PATH

test-driver --shell el-tests/$1
