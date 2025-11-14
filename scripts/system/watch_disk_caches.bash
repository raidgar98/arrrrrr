#!/bin/bash

watch -n 1 "grep -E 'Dirty|Writeback' /proc/meminfo"
