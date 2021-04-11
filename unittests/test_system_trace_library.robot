*** Settings ***
Documentation    Suite description

#Library  SystemTraceLibrary.SystemTraceLibrary  custom_plugins=./
Library  SystemTraceLibrary.SystemTraceLibrary
Library  SSHLibrary
Library  BuiltIn

Suite Setup  run keywords  create host connection  ${HOST}  ${USER}  ${PASSWORD}
...          AND  start trace plugin  aTop  interval=${INTERVAL}  persistent=${PERSISTENT}
#Test Setup   Start period  ${TEST_NAME}
#Test Teardown  generate module statistics  ${TEST_NAME}
Suite Teardown  run keywords  Close host connection
...             AND  generate module statistics

*** Variables ***
${DURATION}  10s
${INTERVAL}  1s
${PERSISTENT}  yes

*** Test Cases ***
Test Time
    [Tags]    DEBUG
    start trace plugin  Time  command=cd ~/bm_noise/linux-5.11.10;make -j 4 clean all  interval=1  name=Complilation
#    start trace plugin  Time  command=ls -l  interval=1  name=HomeDirList
    sleep  ${DURATION}  make something here
    stop trace plugin  Time  name=Complilation
#    generate module statistics  plugin=Time

#Show commands
#     open connection  ${HOST}
#     login  ${USER}  ${PASSWORD}
#     ${out}  ${rc}=  execute command  echo "atop -r ~/atop_temp/atop.dat -b `date +%H:`$((`date +%_M` - 1)) -e `date +%H:%M`"  return_rc=yes
#     log  \nOutput got:\n${out}  console=yes