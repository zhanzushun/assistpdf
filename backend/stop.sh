#!/bin/bash

pid_list=$(ps aux | grep python | grep 'env-openai-latest/' | awk '{print $2}')

for pid in $pid_list; do
    echo "killing process id=$pid"
    kill -9 $pid
done