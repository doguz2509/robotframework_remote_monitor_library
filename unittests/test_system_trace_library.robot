*** Settings ***
Documentation    Suite description

#Library  RemoteMonitorLibrary.RemoteMonitorLibrary  custom_plugins=./
Library  RemoteMonitorLibrary.RemoteMonitorLibrary  start_test=yes  end_test=yes  log_to_db=yes
Library  SSHLibrary
Library  BuiltIn

Suite Setup  Create host monitor  ${HOST}  ${USER}  ${PASSWORD}  certificate=${CERTIFICATE}  timeout=10s

#...          AND  Start monitor plugin  aTop  interval=${INTERVAL}  persistent=${PERSISTENT}
#Test Setup   Start period  ${TEST_NAME}
#Test Teardown  generate module statistics  ${TEST_NAME}
Suite Teardown   run keywords  generate module statistics
...             AND  Terminate all monitors

*** Variables ***
${CERTIFICATE}  ${EMPTY}
${PASSWORD}     ${EMPTY}
${DURATION}  20s
${INTERVAL}  2s
${PERSISTENT}  yes

*** Test Cases ***
Test own keywords
    [Tags]  periods
    start period
    start period  P1
    start period  P2
    wait  20s
    stop period  P1
    stop period  P2
    stop period


Test demo attack
    [Tags]  demo
#    [Setup]  run keywords  open connection  ${HOST}
#    ...         AND  login  ${USER}  ${PASSWORD}

#    start command  echo ""|/opt/morphisec/demo/mlp_attack_demo 2>&1
#    ${out}  ${rc}=  read command output  return_rc=yes
#    log  \nRC: ${rc}\nOutput:\n${out}  console=yes
#    start monitor plugin  SSHLibrary  echo ""|/opt/morphisec/demo/mlp_attack_demo  name=demo_attack
#    ...     rc=137|128  return_rc=yes
#    ...     interval=${INTERVAL}  persistent=${PERSISTENT}  return_stderr=yes  expected=Killed
    sleep  ${DURATION}  make something here
#    [Teardown]  close all connections

Test Host monitor
    [Tags]  monitor
#    [Setup]  Prepare bm
#    Register KW  end_test  fatal error  StamFatal
    Start monitor plugin  aTop  interval=${INTERVAL}  sudo=yes
    add to plugin  aTop  apache  kworker=True
    wait  ${DURATION}
    remove from plugin  aTop  apache  kworker=True
    wait  ${DURATION}
    add to plugin  aTop  apache  kworker=True
    wait  ${DURATION}
    remove from plugin  aTop  apache  kworker=True
    wait  ${DURATION}

#    start monitor plugin  SSHLibrary  echo ""|/opt/morphisec/demo/mlp_attack_demo  return_rc=yes  name=demo_attack
#    ...     return_stderr=yes  rc=137|128|127
#    expected=Killed
#    Start monitor plugin  Time  command=make -j 40 clean all  interval=5s  return_stdout=yes
#    ...                         name=Compilation  start_in_folder=~/bm_noise/linux-5.11.10
#    Start monitor plugin  Time  command=du -hc .  name=Du  interval=${INTERVAL}
#    Start monitor plugin  Time  command=ls -l  name=Ls  interval=${INTERVAL}
#    wait  20s
#    pause monitor  Pause_me
#    wait  20s
#    resume monitor  Pause_me
#    wait  ${DURATION}
#    Stop monitor plugin  Time  name=Complilation  timeout=5m
#    stop monitor plugin  atop
#    generate module statistics  period=${TEST_NAME}  plugin=Time
    generate module statistics  period=${TEST_NAME}  plugin=aTop

#    [Teardown]  terminate_all_monitors

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

*** Keywords ***

Prepare bm
    open connection  ${HOST}
    login with public key  ${USER}  ${CERTIFICATE}
    log  Prepare environment  console=yes
    ${HOME}=  execute command  echo $HOME
    @{comd_list}=  create list
    ...     rm -rf ${HOME}/bm_noise/linux-5.11.10
    ...     cd ${HOME}/bm_noise; tar xvf kernel*
    ...     cp -v /boot/config-$(uname -r) ${HOME}/bm_noise/linux-5.11.10/.config
    ...     cd ${HOME}/bm_noise/linux-5.11.10; make defconfig
    log many  @{comd_list}
    FOR  ${cmd}  IN   @{comd_list}
        ${err}  ${rc}=  execute command  ${cmd}  return_stdout=no  return_rc=yes  return_stderr=yes
        run keyword if  ${rc} > 0  fail  Command: ${cmd} - FAILED [Rc: ${rc}]\n${err}
    END
    log  Environment setup successfully completed  console=yes
    [Teardown]  close connection

