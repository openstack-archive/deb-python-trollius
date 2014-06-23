set -e -x
./update-tulip-step2.sh
tox -e py27,py33
hg ci -m 'Merge Tulip into Trollius'
