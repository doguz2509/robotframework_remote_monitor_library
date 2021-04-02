*** Settings ***
Documentation    Suite description

#Library  system_trace.SystemTraceLibrary  custom_plugins=my_plug.py
Library  system_trace.SystemTraceLibrary
Library  BuiltIn

*** Test Cases ***
Test title
    [Tags]    DEBUG
    create trace connection  ${HOST}  ${USER}  ${PASSWORD}  alias=${TEST_NAME}
#    start trace plugin  atop  interval=1s
    sleep  5s  wait
    close trace connection
    generate module statistics  alias=${TEST_NAME}
*** Keywords ***
Provided precondition
    Setup system under test