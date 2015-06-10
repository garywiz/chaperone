cd /setup
# remove existing chaperone.d and init.d from /apps so none linger
rm -rf /apps/chaperone.d /apps/init.d
# copy everything from setup to the root /apps
tar cvf - --exclude 'build*' --exclude 'run.sh' . | (cd /apps; tar xf -)
# Add additional setup commands for your production image here, if any.
rm -rf /setup
