*** Settings ***
Documentation    Suite description

#Library  system_trace.SystemTraceLibrary  custom_plugins=my_plug.py
Library  system_trace.SystemTraceLibrary
Library  BuiltIn

Suite Setup  run keywords  create host connection  ${HOST}  ${USER}  ${PASSWORD}  alias=${SUITE_NAME}
...          AND  start trace plugin  aTopPlugIn  interval=1s
Test Setup   Start period  ${TEST_NAME}
Test Teardown  run keywords  Stop period   ${TEST_NAME}
...             AND  generate module statistics  ${TEST_NAME}
Suite Teardown  Close host connection  alias=${SUITE_NAME}

*** Test Cases ***
Test 01
    [Tags]    DEBUG
    sleep  10s  wait

Test 02
    [Tags]    DEBUG
    sleep  10s  wait
