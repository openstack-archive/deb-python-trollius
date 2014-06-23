set -e

# Check for merge conflicts
if $(hg resolve -l | grep -q -v '^R'); then
    echo "Fix the following conflicts:"
    hg resolve -l | grep -v '^R'
    exit 1
fi

# Ensure that yield from is not used
if $(hg diff|grep -q 'yield from'); then
    echo "yield from present in changed code!"
    hg diff | grep 'yield from'
    exit 1
fi

# Ensure that mock patchs trollius module, not asyncio>"
if $(grep -q 'patch.*asyncio' tests/*.py); then
    echo "Fix following patch lines in tests/"
    grep 'patch.*asyncio' tests/*.py
    exit 1
fi
