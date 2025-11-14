#/bin/bash


ifstat -i enp4s0 1 | awk 'NR>2 {printf "DOWN: %.2f%%  UP: %.2f%%\n", ($1/125000*100), ($2/125000*100)}'
