*** Settings ***
Documentation    Suite description

Library  system_trace.SystemTraceLibrary  custom_plugins=my_plug.py
#Library  system_trace.SystemTraceLibrary
Library  BuiltIn

*** Test Cases ***
Test title
    [Tags]    DEBUG
    create host connection  ${HOST}  ${USER}  ${PASSWORD}
    start trace plugin  aTopPlugIn  interval=1s
    sleep  10s  wait
    close host connection
    generate module statistics
*** Keywords ***
Provided precondition
    Setup system under test