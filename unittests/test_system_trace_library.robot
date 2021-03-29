*** Settings ***
Documentation    Suite description

Library  system_trace.SystemTraceLibrary  custom_plugins=my_plug.py
Library  BuiltIn

*** Test Cases ***
Test title
    [Tags]    DEBUG
    create connection
    sleep  3  wait

*** Keywords ***
Provided precondition
    Setup system under test