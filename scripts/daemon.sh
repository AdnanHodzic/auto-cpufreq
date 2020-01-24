#!/bin/bash

auto-cpufreq --daemon 2>&1 | tee -a /var/log/auto-cpufreq.log
