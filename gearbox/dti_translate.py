#!/usr/bin/env python

import sys

test = """$name state
#0 ?darkred?V
#5 ?darkblue?H
#10 ?darkblue?H
#20 ?darkblue?H
#30
#40 ?darkblue?H
#55
$finish"""

state_code = {0: '', 1: '?DarkRed?V', 2: '?DarkBlue?R', 3: '?DarkGreen?H'}


def dump_seq(seq):
    # print(f'$name {name}', flush=True)
    print(f'$name --')
    for i, state in seq.items():
        print(f'#{i*10} {state_code[state]}')

    print('$finish')


cur_time = 0
max_time = 0
seq = {0: 0}
cur_val = [0, 0]
for line in sys.stdin:
    if line.startswith('$'):
        if 'data_end' in line:
            dump_seq(seq)
            seq = {0: 0}
            cur_time = 0
            sys.stdout.flush()
            continue
        elif line.startswith('$comment name'):
            name = line.split()[2]
        else:
            continue
    elif line.startswith('#'):
        next_time = int(line[1:]) // 10
        if seq[cur_time] == 3:
            for t in range(cur_time + 1, next_time):
                seq[t] = seq[cur_time]
        cur_time = next_time
    else:
        val = int(line[0])
        pos = int(line[1]) - 1
        cur_val[pos] = val

        seq[cur_time] = (cur_val[1] << 1) + cur_val[0]

        # seq[cur_time] = int(line.split()[0][1:], 2)
