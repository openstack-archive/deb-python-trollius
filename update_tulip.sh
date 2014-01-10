set -e -x
hg update default
hg pull https://code.google.com/p/tulip/
hg update
hg update trollius
set +x
echo "Now type:"
echo "hg merge default"
echo "<fix conflicts>"
echo "hg ci -m 'Merge Tulip into Trollius'"
