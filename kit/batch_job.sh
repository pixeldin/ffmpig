#!/bin/bash

spwd=$(pwd)
# job1
# target dir
cd "/f/tmp/"
echo -e "jump to $(pwd), filelist: \n$(ls)\n" | tee -a $spwd/batch.log

# job2
cd "/f/tmp/"
echo -e "jump to $(pwd), filelist: \n$(ls)\n" | tee -a $spwd/batch.log


wait
echo "job list finished."
