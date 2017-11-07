'''
Follow these steps to configure the webhook in Slack:

  1. Navigate to https://<your-team-domain>.slack.com/services/new

  2. Search for and select "Incoming WebHooks".

  3. Choose the default channel where messages will be sent and click "Add Incoming WebHooks Integration".

  4. Copy the webhook URL from the setup instructions and use it in the next section.

To encrypt your secrets use the following steps:

  1. Create or use an existing KMS Key - http://docs.aws.amazon.com/kms/latest/developerguide/create-keys.html

  2. Click the "Enable Encryption Helpers" checkbox

  3. Paste <SLACK_CHANNEL> into the slackChannel environment variable

  Note: The Slack channel does not contain private info, so do NOT click encrypt

  4. Paste <SLACK_HOOK_URL> into the kmsEncryptedHookUrl environment variable and click encrypt

  Note: You must exclude the protocol from the URL (e.g. "hooks.slack.com/services/abc123").

  5. Give your function's role permission for the kms:Decrypt action.

     Example:

{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "Stmt1443036478000",
            "Effect": "Allow",
            "Action": [
                "kms:Decrypt"
            ],
            "Resource": [
                "<your KMS key ARN>"
            ]
        }
    ]
}
'''
from __future__ import print_function

import boto3
import json
import logging
import os

from base64 import b64decode
from urllib2 import Request, urlopen, URLError, HTTPError


# The base-64 encoded, encrypted key (CiphertextBlob) stored in the kmsEncryptedHookUrl environment variable
ENCRYPTED_HOOK_URL = os.environ['kmsEncryptedHookUrl']
# The Slack channel to send a message to stored in the slackChannel environment variable
SLACK_CHANNEL = os.environ['slackChannel']

HOOK_URL = "https://" + boto3.client('kms').decrypt(CiphertextBlob=b64decode(ENCRYPTED_HOOK_URL))['Plaintext']

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.info("Event: " + str(event))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    logger.info("Message: " + str(message))

    pipeline = message['detail']['pipeline'] 
    #old_state = message['OldStateValue']
    new_state = message['detail']['state']
    # reason = message['NewStateReason']

    slack_message_text = "Status: %s\n" % new_state

    cp_client = boto3.client('codepipeline')
    response = cp_client.get_pipeline_state(name=pipeline)

    # formatted for UDN Gateway Codepipeline
    try:
      pipeline_id = response['stageStates'][0]['latestExecution']['pipelineExecutionId']
    except:
      pass
    else:
      slack_message_text += "%s pipeline ID: %s\n" % (pipeline, pipeline_id)

    try:
      revision_url = response['stageStates'][0]['actionStates'][0]['revisionUrl']
    except:
      pass
    else:
      slack_message_text += "Github commit: %s\n" % revision_url

    slack_message = {
        'username': 'AWS CodePipeline',
        'text': slack_message_text
    }

    req = Request(HOOK_URL, json.dumps(slack_message))
    try:
        response = urlopen(req)
        response.read()
    except HTTPError as e:
        logger.error("Request failed: %d %s", e.code, e.reason)
    except URLError as e:
        logger.error("Server connection failed: %s", e.reason)
