#!/usr/bin/env python


template = r'''
#!/bin/bash
#
# This script is ***AUTOGENERATED***
#
# This is a script for applying and removing xt_bpf iptable rule. This
# particular rule was created to match packets that look like DNS and
# are against the following domains:
#
#     %(domains)s
#
# To apply the iptables bpf rule run:
#
#    ./%(name)s 1.1.1.1 2.2.2.2
#
# With the ip addresses of flooded name servers - destination IP of
# the packets.
#
# To clean the iptables rule:
#
#    ./%(name)s --delete
#
#
# For the record, here's the BPF assembly:
#
%(assembly)s
#

set -o noclobber
set -o errexit
set -o nounset
set -o pipefail

: ${IPTABLES:="iptables"}
: ${IPSET:="ipset"}
: ${INPUTPLACE:="4"}
: ${DEFAULTINT:=`awk 'BEGIN {n=0} $2 == "00000000" {n=1; print $1; exit} END {if (n=0) {print "eth0"}}' /proc/net/route`}

iptablesrule () {
    ${IPTABLES} \
        ${*} \
        -i ${DEFAULTINT} \
        -p udp --dport 53 \
        -m set --match-set %(name)s dst \
        -m bpf --bytecode "%(bytecode)s" \
        -j DROP
}

if [ "$*" == "--delete" ]; then

    A=`(iptablesrule -C INPUT || echo "error") 2>/dev/null`
    if [ "${A}" != "error" ]; then
        iptablesrule -D INPUT
    fi
    ${IPSET} -exist destroy %(name)s 2>/dev/null

else

    ${IPSET} -exist create %(name)s hash:ip
    while [ "$*" != "" ]; do
        ${IPSET} -exist add %(name)s "$1"
        shift
    done

    A=`(iptablesrule -C INPUT || echo "error") 2>/dev/null`
    if [ "${A}" == "error" ]; then
        iptablesrule -I INPUT ${INPUTPLACE}
    fi

fi
'''.lstrip()

import sys
import subprocess
import string
import os
import stat


for p in sys.argv[1:]:
    if p[0] == '-':
        print "pass only domains"
        sys.exit(-1)

domains = sys.argv[1:]

if not domains:
    print "at least one domain"
    sys.exit(-1)

bytecode = subprocess.check_output(['./bpf_dns.py', '-o0'] + domains)
assembly = subprocess.check_output(['./bpf_dns.py', '-o0', '-s'] + domains)

name_parts = []
if True:
    for domain in domains:
        domain = domain.strip(".").strip()

        parts = []
        for part in domain.split("."):
            if part == '*':
                parts.append( 'any' )
            else:
                parts.append( ''.join(c if c in string.printable and c not in string.whitespace else 'x'
                                      for c in part) )
        name_parts.append( '_'.join(parts) )
name = 'bpf_dns_' + '_'.join(name_parts)



fname = name + '.sh'

with open(fname, 'wb') as f:
    f.write(template % {
            'domains': ' '.join(domains),
            'bytecode': bytecode.strip(),
            'assembly': '#    ' + '\n#    '.join(assembly.split('\n')),
            'name': name,
            })
os.chmod(fname, 0750)
print "Generated file %s" % (fname,)
