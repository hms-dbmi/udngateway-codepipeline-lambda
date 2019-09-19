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

    try:
        subject = event['Records'][0]['Sns']['Subject']
    except KeyError, ValueError:
        subject = 'status'

    if 'APPROVAL NEEDED' in subject:
        message_text = _get_approval_message(event)
    else:
        message_text = _get_status_message(event)

    slack_message = {
        'username': 'AWS CodePipeline',
        'text': message_text
    }

    req = Request(HOOK_URL, json.dumps(slack_message))
    try:
        response = urlopen(req)
        response.read()
    except HTTPError as e:
        logger.error("Request failed: %d %s", e.code, e.reason)
    except URLError as e:
        logger.error("Server connection failed: %s", e.reason)


def _get_approval_message(event):
    """
    handles approval events
    :param event:
    :return:
    """
    message = event['Records'][0]['Sns']['Message']
    link = message.split('\n\n')[5]
    pipeline_name = message.split('\n\n')[3]

    return '\n*APPROVAL NEEDED*\n{pipeline_name}\n{link}'.format(pipeline_name=pipeline_name, link=link)


def _get_status_message(event):
    """
    handles status events
    :param event:
    :return:
    """
    message = json.loads(event['Records'][0]['Sns']['Message'])

    pipeline_name = message['detail']['pipeline'] 
    new_state = message['detail']['state']

    slack_message_text = "*Status:* %s\n" % new_state

    execution_id = message['detail']['execution-id']    
    slack_message_text += "%s pipeline ID: %s\n" % (pipeline_name, execution_id)

    cp_client = boto3.client('codepipeline')

    if new_state == 'SUCCEEDED':
      response = cp_client.get_pipeline_execution(pipelineName=pipeline_name, pipelineExecutionId=execution_id)
      try:
        revision_url = response['pipelineExecution']['artifactRevisions'][0]['revisionUrl']
        revision_summary = response['pipelineExecution']['artifactRevisions'][0]['revisionSummary']
      except:
        pass
      else:
        slack_message_text += ">>> Summary: %s\n" % revision_summary
        slack_message_text += "Github commit: %s\n" % revision_url

    if new_state == 'FAILED':
      response = cp_client.get_pipeline_state(name=pipeline_name)
      try:
        codebuild_url = response['stageStates'][1]['actionStates'][0]['latestExecution']['externalExecutionUrl']
      except:
        codebuild_url = 'Error locating logs'
      else:
        slack_message_text += 'Build logs: %s' % codebuild_url

    return slack_message_text

