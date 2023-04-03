#!/bin/bash

# job1
sleep 3 &
# job2
sleep 3 &

sleep 1 
wait
echo "job list finished."
