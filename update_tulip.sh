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
echo "hg diff|grep 'yield from'"
echo "<ensure that mock patchs trollius module, not asyncio>"
echo "grep 'patch.*asyncio' tests/*py"
echo "<run tests>"
echo "hg ci -m 'Merge Tulip into Trollius'"
