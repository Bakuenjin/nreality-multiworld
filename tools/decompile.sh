#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p .local/analysis
export_one() {
  java -Duser.home="$PWD/.local/tools/java-home" \
    -jar .local/tools/ffdec/ffdec.jar -export script \
    ".local/analysis/$1" ".local/original/$2" \
    > ".local/analysis/$1-export.log" 2>&1
}
export_one nreality NReality_v6g2.swf
export_one base n_v14.swf
for n in 10 11 12 13 14 15 16 17 18 19; do
  export_one "col$n" "col$n.swf"
done
