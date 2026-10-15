#!/bin/sh
# Build an isolated replay snapshot: HEAD src/ plus the given owned working-tree files.
# usage: make_snapshot.sh <dest_src_dir> [owned src-relative path ...]
# Other files come from HEAD, so uncommitted edits of other workers never enter the replay.
set -e
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
DEST="$1"; shift
rm -rf "$DEST"; mkdir -p "$DEST"
git archive HEAD src | tar -x -C "$DEST" --strip-components=1
for f in "$@"; do
  cp "$f" "$DEST/${f#src/}"
done
echo "snapshot $DEST"
