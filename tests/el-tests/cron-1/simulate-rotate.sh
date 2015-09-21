echo simulating rotation
echo SIMULATE-ROTATE SERIAL NUMBER: $(get-serial)
service=$1
telchap=$2
$(is-running apache2) && echo apache is running || echo apache is NOT running
ps axf
if [ "$telchap" != "telchap" ]; then
  sudo kill `cat /run/apache2/apache2.pid`  # chaperone doesn't know this
  echo DIRECT KILL of $service
else
  echo Use TELCHAP to tell Chaperone to kill $service
fi
telchap reset $service
sleep 1
$(is-running apache2) && echo apache is running || echo apache is NOT running
ps axf
telchap start $service
sleep 1
$(is-running apache2) && echo apache is running || echo apache is NOT running
ps axf
