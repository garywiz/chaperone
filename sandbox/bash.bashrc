PS1="image:\W$ "
if [ "$EMACS" == "t" ]; then
  stty -echo
fi
# Created by chaplocal
cd $APPS_DIR
echo ""
echo "Now running inside container. Directory is: $APPS_DIR"
echo ""
