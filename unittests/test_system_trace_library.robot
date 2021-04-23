*** Settings ***
Documentation    Suite description

#Library  RemoteMonitorLibrary.RemoteMonitorLibrary  custom_plugins=./
Library  RemoteMonitorLibrary.RemoteMonitorLibrary  start_test=yes  end_test=yes
Library  SSHLibrary
Library  BuiltIn

Suite Setup  Create host monitor  ${HOST}  ${USER}  ${PASSWORD}  timeout=10s
#...          AND  Start monitor plugin  aTop  interval=${INTERVAL}  persistent=${PERSISTENT}
#Test Setup   Start period  ${TEST_NAME}
#Test Teardown  generate module statistics  ${TEST_NAME}
Suite Teardown   close_all_host_monitors
#...             AND  generate module statistics  plugin=aTop

*** Variables ***
${DURATION}  10s
${INTERVAL}  0.5s
${PERSISTENT}  yes

*** Test Cases ***

Test demo attack
    [Tags]  demo
#    [Setup]  run keywords  open connection  ${HOST}
#    ...         AND  login  ${USER}  ${PASSWORD}

#    start command  echo ""|/opt/morphisec/demo/mlp_attack_demo 2>&1
#    ${out}  ${rc}=  read command output  return_rc=yes
#    log  \nRC: ${rc}\nOutput:\n${out}  console=yes
    start monitor plugin  SSHLibrary  echo ""|/opt/morphisec/demo/mlp_attack_demo  rc=137|128  return_rc=yes
    ...     interval=${INTERVAL}  persistent=${PERSISTENT}  return_stderr=yes  expected=Killed
    sleep  ${DURATION}  make something here
#    [Teardown]  close all connections

Test Host monitor
    [Tags]  monitor
#    [Setup]  Create host monitor  ${HOST}  ${USER}  ${PASSWORD}
    Start monitor plugin  aTop  interval=${INTERVAL}  persistent=${PERSISTENT}  sudo=yes
#    start monitor plugin  SSHLibrary  echo ""|/opt/morphisec/demo/mlp_attack_demo  rc=137|128  return_rc=yes
#    ...     persistent=${PERSISTENT}  return_stderr=yes  expected=Killed
#    Start monitor plugin  Time  command=make -j 20 clean all  persistent=${PERSISTENT}
#    ...                         name=Compilation  start_in_folder=~/bm_noise/linux-5.11.10  store_output=yes
#    Start monitor plugin  Time  command=ls -l  name=HomeDirList  store_output=yes  interval=1s

    sleep  ${DURATION}  make something here
#    Stop monitor plugin  Time  name=Complilation
#    stop monitor plugin  atop
#    generate module statistics  plugin=Time  name=Compilation
#    generate module statistics  plugin=Time  name=HomeDirList
    generate module statistics  plugin=aTop

    [Teardown]  close_all_host_monitors

#Test statistic
#    [Tags]  systrace_test
#    [Setup]  create host monitor  ${HOST}  ${USER}  ${PASSWORD}
#    start monitor plugin  aTop  interval=5s}  persistent=yes
#    start monitor plugin  Time  interval=${INTERVAL}  persistent=yes
#    ...                   command=make -j 10 clean all  name=BM  start_folder=~/bm_noise/linux-5.11.10
#    sleep   5h
#    [Teardown]  run keywords  generate module statistics  AND  close all connections

#Show commands
#     open connection  ${HOST}
#     login  ${USER}  ${PASSWORD}
#     ${out}  ${rc}=  execute command  echo "atop -r ~/atop_temp/atop.dat -b `date +%H:`$((`date +%_M` - 1)) -e `date +%H:%M`"  return_rc=yes
#     log  \nOutput got:\n${out}  console=yes