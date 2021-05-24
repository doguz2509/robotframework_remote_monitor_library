*** Settings ***
Documentation    Suite description
Library  RemoteMonitorLibrary.RemoteMonitorLibrary  log_to_db=yes
...      start_test=start_test_kw  end_test=end_test_kw
...      start_suite=start_suite_kw  end_suite=end_suite_kw
Library  BuiltIn

Suite Setup  Create host monitor  ${HOST}  ${USER}  ${PASSWORD}  timeout=10s
#...         AND  Start monitor plugin  aTop  interval=1s  sudo=yes

#Suite Teardown   run keywords  close_all_host_monitors
#...             AND  generate module statistics

Force Tags  listener

*** Test Cases ***
Test own listeners
    wait  5s

Test test's name with single quote char
    wait  5s
    [Teardown]  stop period  ${TEST_NAME}
*** Keywords ***

start_suite_kw
    log  Suite ${SUITE_NAME} started

end_suite_kw
    log  Suite ${SUITE_NAME} ended

start_test_kw
    log  Test ${TEST_NAME} started

end_test_kw
    log  Test ${TEST_NAME} ended