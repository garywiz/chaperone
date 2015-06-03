#!/bin/bash

# the cd trick assures this works even if the current directory is not current.
cd ${0%/*}
./setup-bin/build -x
docker tag chaperone-devbase chaperone-base
