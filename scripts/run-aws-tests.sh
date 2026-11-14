#!/usr/bin/env bash
# Run the Robot (browser) and Postman (API) tests against the AWS deployment.
#
# Usage (from the repo root):
#   ./scripts/run-aws-tests.sh          both suites
#   ./scripts/run-aws-tests.sh robot    Robot only
#   ./scripts/run-aws-tests.sh newman   Postman only
#
# Asks for a Cognito test account's email and password once. The password is
# not shown, not saved and not written to any report.
#
# Reports (git-ignored):
#   tests/robot/results/report.html     tests/postman/results/report.html
#
# Each Postman run creates one "Postman Test Org" in the account, and there is
# no way to delete an organization yet, so use a spare test account.
#
# Needs: Python 3, Google Chrome and Node.js (for npx).

set -euo pipefail

cd "$(dirname "$0")/.."

SUITES="${1:-all}"
case "$SUITES" in
  all | robot | newman) ;;
  *) echo "Usage: $0 [robot|newman]" >&2; exit 1 ;;
esac

# The deployed site, and the web app's Cognito client id (public: it is in the
# site's JavaScript). Override either one with an environment variable.
URL="${WT_URL:-http://warrantytrack-276388427.ap-southeast-1.elb.amazonaws.com}"
CLIENT_ID="${WT_COGNITO_CLIENT_ID:-52nhei8og2k4hj1b8anbca0n94}"
REGION="${WT_COGNITO_REGION:-ap-southeast-1}"

read -r -p "Test account email: " EMAIL
read -r -s -p "Password: " PASSWORD
echo

run_robot() {
  echo "==> Robot: add_asset.robot on $URL"
  cd tests/robot
  if [ ! -d .venv ]; then
    python3 -m venv .venv
  fi
  .venv/bin/pip install -q -r requirements.txt
  # Not "set -e" for this line: a failed test should still show its report.
  .venv/bin/robot --outputdir results \
    --variable "URL:$URL" --variable "EMAIL:$EMAIL" --variable "PASSWORD:$PASSWORD" \
    add_asset.robot || true
  cd ../..
  echo "    Report: tests/robot/results/report.html"
}

run_newman() {
  echo "==> Postman: signing in to Cognito for an API token"
  # The same sign-in call the website makes. Python's standard library only.
  TOKEN=$(EMAIL="$EMAIL" PASSWORD="$PASSWORD" CLIENT_ID="$CLIENT_ID" REGION="$REGION" python3 - <<'PY'
import json, os, sys, urllib.error, urllib.request

body = json.dumps({
    "AuthFlow": "USER_PASSWORD_AUTH",
    "ClientId": os.environ["CLIENT_ID"],
    "AuthParameters": {"USERNAME": os.environ["EMAIL"], "PASSWORD": os.environ["PASSWORD"]},
}).encode()
request = urllib.request.Request(
    f"https://cognito-idp.{os.environ['REGION']}.amazonaws.com/",
    data=body,
    headers={
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
    },
)
try:
    print(json.load(urllib.request.urlopen(request))["AuthenticationResult"]["IdToken"])
except urllib.error.HTTPError as error:
    sys.exit(f"Cognito sign-in failed: {json.load(error).get('message', error)}")
PY
  )

  echo "==> Postman: WarrantyTrack collection on $URL/api"
  cd tests/postman
  # skipHeaders keeps the token out of the HTML report.
  npx -y -p newman@6.2.1 -p newman-reporter-htmlextra@1.23.1 newman run WarrantyTrack.postman_collection.json \
    -e environments/aws.postman_environment.json --working-dir . \
    --env-var "baseUrl=$URL/api" --env-var "token=$TOKEN" \
    --reporters cli,htmlextra \
    --reporter-htmlextra-export results/report.html \
    --reporter-htmlextra-skipHeaders Authorization \
    --reporter-htmlextra-title "WarrantyTrack API tests (AWS)" || true
  cd ../..
  unset TOKEN
  echo "    Report: tests/postman/results/report.html"
}

if [ "$SUITES" = all ] || [ "$SUITES" = robot ]; then run_robot; fi
if [ "$SUITES" = all ] || [ "$SUITES" = newman ]; then run_newman; fi

unset PASSWORD
echo "==> Done"
