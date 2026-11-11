*** Settings ***
Documentation       Add an asset from a receipt, end to end in a real browser (CLOUDAPPG5-134).
...
...                 Sign in, choose the personal workspace, upload a receipt, check the
...                 details read from it, finish the warranty and serial number, save,
...                 then find the new asset in the Assets list.
...
...                 Locally (docker compose, AUTH_BACKEND=dev) any email and password work.
...                 Against AWS, pass a Cognito test account and the deployed URL:
...                 robot --variable URL:https://... --variable EMAIL:... --variable PASSWORD:... add_asset.robot
...
...                 Each step is its own test case, like the course example, so the report
...                 shows which step failed. The steps depend on each other and must run in order.

Library             SeleniumLibrary
Library             DateTime

Suite Teardown      Close All Browsers


*** Variables ***
${URL}              http://localhost:3000
${BROWSER}          headlesschrome
${EMAIL}            test@warrantytrack.io
${PASSWORD}         Test1234!
${DELAY}            0.2
${RECEIPT}          ${CURDIR}/files/sample-receipt.png
# What the receipt says. Locally the fake OCR always returns this product.
${PRODUCT}          Dell Latitude 5540
${INVOICE}          PB-2026-1101
${PURCHASE_DATE}    2026-11-01
${EXPIRY_LABEL}     1 Nov 2028


*** Test Cases ***
1. Open Browser
    Open Browser    ${URL}/login    ${BROWSER}
    Set Window Size    1440    900
    Set Selenium Speed    ${DELAY}
    Wait Until Page Contains    Sign in to your account

2. Sign In
    Input Text    id:email    ${EMAIL}
    Input Password    id:password    ${PASSWORD}
    Click Button    Sign In
    Wait Until Location Contains    /workspace    timeout=20s
    Wait Until Page Contains    Choose your workspace

3. Choose Personal Workspace
    # Clicking a card selects it. Only the selected card's Continue is a working link.
    Click Element    xpath://button[.//*[normalize-space(text())='Personal Workspace']]
    Click Link    xpath://*[normalize-space(text())='Personal Workspace']/ancestor::div[.//a[normalize-space()='Continue']][1]//a[normalize-space()='Continue']
    Wait Until Location Contains    /dashboard    timeout=20s

4. Open Add Asset
    Click Link    Add Asset
    Wait Until Page Contains    Scan the receipt, or enter the details yourself.

5. Upload Receipt And Check The Extracted Details
    Choose File    id:receipt-file    ${RECEIPT}
    # The button stays disabled until the receipt has been uploaded and read.
    Wait Until Page Contains    Receipt read    timeout=90s
    Click Button    Continue to review
    Wait Until Page Contains    Review extracted information    timeout=90s
    Textfield Value Should Be    id:product-name    ${PRODUCT}
    ${vendor}=    Get Value    id:vendor
    Should Not Be Empty    ${vendor}    msg=The vendor was not read from the receipt.
    Capture Page Screenshot

6. Complete Purchase And Warranty Details
    Set Date    purchase-date    ${PURCHASE_DATE}
    Input Text    id:invoice-number    ${INVOICE}
    Input Text    id:category    Laptop
    Select From List By Value    id:condition    new
    Input Text    id:warranty-provider    Dell
    Set Date    warranty-start    ${PURCHASE_DATE}
    Select From List By Label    id:warranty-duration    2 years
    Wait Until Page Contains    ${EXPIRY_LABEL}
    Click Button    Confirm

7. Enter A Unique Serial Number
    Wait Until Element Is Visible    id:serial-number
    ${stamp}=    Get Current Date    result_format=%Y%m%d%H%M%S
    Set Suite Variable    ${SERIAL}    RF-${stamp}
    Input Text    id:serial-number    ${SERIAL}
    Click Button    Confirm

8. Add A Box Note And Save
    Wait Until Page Contains    Add a photo of the box
    Input Text    id:box-note    Box is on the top shelf
    Click Button    Save asset
    Wait Until Page Contains    Asset saved successfully    timeout=20s
    Location Should Contain    /dashboard
    Capture Page Screenshot

9. Find The New Asset In The Assets List
    Go To    ${URL}/assets
    Wait Until Element Is Visible    xpath://input[contains(@placeholder, 'Search')]
    Input Text    xpath://input[contains(@placeholder, 'Search')]    ${SERIAL}
    Wait Until Page Contains    ${SERIAL}    timeout=15s
    Page Should Contain    ${PRODUCT}
    Capture Page Screenshot

10. Close Browser
    Close Browser


*** Keywords ***
Set Date
    [Documentation]    Sets a date input to an ISO date (YYYY-MM-DD).
    ...    Typing into a date picker depends on the browser's language, so this sets
    ...    the value directly and fires the input event React listens for.
    [Arguments]    ${id}    ${iso_date}
    Execute Javascript
    ...    const input = document.getElementById('${id}');
    ...    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    ...    setValue.call(input, '${iso_date}');
    ...    input.dispatchEvent(new Event('input', { bubbles: true }));
