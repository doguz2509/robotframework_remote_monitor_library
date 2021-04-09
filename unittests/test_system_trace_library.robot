*** Settings ***
Documentation    Suite description

#Library  SystemTraceLibrary.SystemTraceLibrary  custom_plugins=./
Library  SystemTraceLibrary.SystemTraceLibrary
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
    start trace plugin  Time  command=ls -l
    sleep  ${DURATION}  make something here
    stop trace plugin  Time
    generate module statistics  plugin=Time

Test 02
    [Tags]    DEBUG
    sleep  ${DURATION}  make something again here
