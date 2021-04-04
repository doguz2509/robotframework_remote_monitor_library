*** Settings ***
Documentation    Suite description

#Library  system_trace.SystemTraceLibrary  custom_plugins=my_plug.py
Library  system_trace.SystemTraceLibrary
Library  BuiltIn

Suite Setup  run keywords  create host connection  ${HOST}  ${USER}  ${PASSWORD}  alias=${SUITE_NAME}
...          AND  start trace plugin  aTopPlugIn  interval=0.5s
Test Setup   Start period  ${TEST_NAME}
Test Teardown  run keywords  Stop period   ${TEST_NAME}
...             AND  generate module statistics  ${TEST_NAME}
Suite Teardown  run keywords  Close host connection  alias=${SUITE_NAME}
...             AND  generate module statistics

*** Variables ***
${DURATION}  10s

*** Test Cases ***
Test 01
    [Tags]    DEBUG
    sleep  ${DURATION}  make something here

Test 02
    [Tags]    DEBUG
    sleep  ${DURATION}  make something again here
