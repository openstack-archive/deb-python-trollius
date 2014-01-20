set -e -x
hg update trollius
hg pull --update
hg update default
hg pull https://code.google.com/p/tulip/
hg update
hg update trollius
set +x
echo "Now type:"
echo "hg merge default"
echo "<fix conflicts>"
echo "<ensure that yield from is not used>"
echo "<run tests>"
echo "hg ci -m 'Merge Tulip into Trollius'"
