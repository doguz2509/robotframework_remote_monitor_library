*** Settings ***
Documentation    Suite description

#Library  RemoteMonitorLibrary.RemoteMonitorLibrary  custom_plugins=./
Library  RemoteMonitorLibrary.RemoteMonitorLibrary
Library  SSHLibrary
Library  BuiltIn

Suite Setup  run keywords  Create host monitor  ${HOST}  ${USER}  ${PASSWORD}
...          AND  Start monitor plugin  aTop  interval=${INTERVAL}  persistent=${PERSISTENT}
#Test Setup   Start period  ${TEST_NAME}
#Test Teardown  generate module statistics  ${TEST_NAME}
Suite Teardown  run keywords  Close host monitor
...             AND  generate module statistics  plugin=aTop

*** Variables ***
${DURATION}  10s
${INTERVAL}  0.5s
${PERSISTENT}  yes

*** Test Cases ***
Test Time
    [Tags]    DEBUG
    Start monitor plugin  Time  command=make -j 10 clean all  interval=0.5s
    ...                         name=Compilation  start_folder=~/bm_noise/linux-5.11.10
#    Start monitor plugin  Time  command=ls -l  interval=1  name=HomeDirList
    sleep  ${DURATION}  make something here
    Stop monitor plugin  Time  name=Complilation
    generate module statistics  plugin=Time  name=Complilation

Test statistic
    [Tags]  systrace_test
    [Setup]  create host monitor  ${HOST}  ${USER}  ${PASSWORD}
    start monitor plugin  aTop  interval=5s}  persistent=yes
    start monitor plugin  Time  interval=${INTERVAL}  persistent=yes
    ...                   command=make -j 10 clean all  name=BM  start_folder=~/bm_noise/linux-5.11.10
    sleep   5h
    [Teardown]  run keywords  generate module statistics  AND  close all connections

#Show commands
#     open connection  ${HOST}
#     login  ${USER}  ${PASSWORD}
#     ${out}  ${rc}=  execute command  echo "atop -r ~/atop_temp/atop.dat -b `date +%H:`$((`date +%_M` - 1)) -e `date +%H:%M`"  return_rc=yes
#     log  \nOutput got:\n${out}  console=yes