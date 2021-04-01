*** Settings ***
Documentation    Suite description

Library  system_trace.SystemTraceLibrary  custom_plugins=my_plug.py
Library  BuiltIn

*** Test Cases ***
Test title
    [Tags]    DEBUG
    create trace connection  ${HOST}  ${USER}  ${PASSWORD}
    start trace plugin  atop  interval=60s  run_as_sudo=true
    sleep  3  wait
    close trace connection

*** Keywords ***
Provided precondition
    Setup system under test