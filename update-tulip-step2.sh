set -e -x

# Check for merge conflicts
hg resolve -l

# Ensure that yield from is not used
if [ ! $(hg diff|grep -q 'yield from') ]; then
    echo "yield from present in changed code!"
    exit 1
fi

# Ensure that mock patchs trollius module, not asyncio>"
if [ $(grep -q 'patch.*asyncio' "tests/*py") ]; then
    echo "Fix following lines in tests/"
    grep 'patch.*asyncio' "tests/*py"
    exit 1
fi
