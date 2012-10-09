#!/bin/bash
# codevalidator.py SVN pre-commit hook (move this file to svnrepo/hooks/pre-commit)
# codevalidator.py must be in PATH!

REPOS="$1"
TXN="$2"

SVNLOOK=/usr/bin/svnlook

FILES=`$SVNLOOK changed -t "$TXN" "$REPOS" | grep -E '^(U|A)' | cut -b5- `

if [ -z "${FILES}" ]; then
    exit 0
fi

tmpdir=`mktemp -d /tmp/codevalidator.XXXXX`
tmpnam_prefix="$tmpdir/"

cv_files=""
for FILE in ${FILES}; do
    tmpnam_src="${tmpnam_prefix}${FILE//\//.}"
    $SVNLOOK cat -t "$TXN" "$REPOS" "${FILE}" >"${tmpnam_src}"
    cv_files="${cv_files} ${tmpnam_src}"
done;

if [ -z "${cv_files}" ]; then
    exit 0
fi

if (! codevalidator.py -v ${cv_files} >"${tmpnam_prefix}messages") then
    echo "codevalidator.py found validation errors:" 1>&2
    cat "${tmpnam_prefix}messages" 1>&2
    rm -rf $tmpdir
    exit 2
fi
rm -rf $tmpdir
