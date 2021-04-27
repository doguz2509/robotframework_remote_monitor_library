*** Settings ***
Documentation    Suite description

#Library  RemoteMonitorLibrary.RemoteMonitorLibrary  custom_plugins=./
Library  RemoteMonitorLibrary.RemoteMonitorLibrary  start_test=yes  end_test=yes
Library  SSHLibrary
Library  BuiltIn

Suite Setup  Create host monitor  ${HOST}  ${USER}  ${PASSWORD}  certificate=${CERTIFICATE}  timeout=10s  log_to_db=yes
#...          AND  Start monitor plugin  aTop  interval=${INTERVAL}  persistent=${PERSISTENT}
#Test Setup   Start period  ${TEST_NAME}
#Test Teardown  generate module statistics  ${TEST_NAME}
Suite Teardown   run keywords  close_all_host_monitors
...             AND  generate module statistics  plugin=aTop

*** Variables ***
${CERTIFICATE}  ${EMPTY}
${PASSWORD}     ${EMPTY}
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
#    Start monitor plugin  aTop  interval=${INTERVAL}  sudo=yes
#    start monitor plugin  SSHLibrary  echo ""|/opt/morphisec/demo/mlp_attack_demo  return_rc=yes
#    ...     return_stderr=yes  rc=137|128|127
#    expected=Killed
    Start monitor plugin  Time  command=make -j 40 clean all  timeout=10m
    ...                         name=Compilation  start_in_folder=~/bm_noise/linux-5.11
    Start monitor plugin  Time  command=ls -l  name=Compilation  interval=10s  store_output=yes

    wait  ${DURATION}
#    Stop monitor plugin  Time  name=Complilation
#    stop monitor plugin  atop
    generate module statistics  period=${TEST_NAME}  plugin=Time  name=Compilation
    generate module statistics  period=${TEST_NAME}  plugin=aTop

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