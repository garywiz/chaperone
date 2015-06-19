PS1="image:\W$ "
if [ "$EMACS" == "t" ]; then
  stty -echo
fi
cd $APPS_DIR/..
PATH=$PWD/bin:$PATH
cd $APPS_DIR
echo ""
echo "Now running inside container. Directory is: $APPS_DIR"
echo ""
