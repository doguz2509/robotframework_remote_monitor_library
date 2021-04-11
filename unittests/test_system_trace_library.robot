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
    Start monitor plugin  Time  command=make -j 4 clean all 2>&1  interval=1
    ...                         name=Complilation  start_folder=~/bm_noise/linux-5.11.10
#    Start monitor plugin  Time  command=ls -l  interval=1  name=HomeDirList
    sleep  ${DURATION}  make something here
    Stop monitor plugin  Time  name=Complilation
    generate module statistics  plugin=Time  name=Complilation

#Show commands
#     open connection  ${HOST}
#     login  ${USER}  ${PASSWORD}
#     ${out}  ${rc}=  execute command  echo "atop -r ~/atop_temp/atop.dat -b `date +%H:`$((`date +%_M` - 1)) -e `date +%H:%M`"  return_rc=yes
#     log  \nOutput got:\n${out}  console=yes