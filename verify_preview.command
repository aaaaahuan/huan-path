#!/bin/zsh
# Run in a normal local terminal; current agent sandbox disallows browser Mach IPC.
cd "${0:A:h}"
node work/browser-test/verify.cjs
