"""Pipes and Filters chain applied to every message read from Redis.

main.py is the pipe source: it reads raw items from the Redis
subscription and feeds them, one at a time, into FILTERS, in order.
Each filter here only knows about the message it receives and the one it
returns, never about Redis, Zipkin, or any other filter.

A filter has one of two outcomes:
- it returns a PipelineContext, and the message moves to the next filter
- it returns None, and the message is dropped, no error involved

If a filter raises an exception instead, that is treated as a failure of
the pipeline, not a normal rejection, and notify_error is invoked.
"""

import json
import os
import time

import requests

REQUIRED_FIELDS = ('opName', 'username', 'todoId')


class PipelineContext:
    """Carries one message through the filter chain.

    raw_item is the original item as returned by Redis pubsub. message is
    filled in by validate() once the payload is confirmed to be real
    data, not a Redis protocol control event.
    """

    def __init__(self, raw_item):
        self.raw_item = raw_item
        self.message = None


def validate(ctx):
    """First filter: is this raw_item a real data message from todos-api?

    Redis pubsub also delivers protocol control messages through the same
    listen() loop, most notably the subscribe confirmation sent once when
    the process starts. Those are not JSON payloads and are rejected here
    by type, not by letting json.loads fail and catching the exception.
    """
    if ctx.raw_item.get('type') != 'message':
        return None

    try:
        payload = json.loads(ctx.raw_item['data'].decode('utf-8'))
    except (UnicodeDecodeError, ValueError, AttributeError) as e:
        print('validate: could not parse message as JSON: {}'.format(e))
        return None

    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        print('validate: message missing required fields {}: {}'.format(missing, payload))
        return None

    ctx.message = payload
    return ctx


def enrich(ctx):
    """Second filter: adds metadata that validate does not produce."""
    ctx.message['processed_at'] = time.time()
    ctx.message['processed_by'] = 'log-message-processor'
    return ctx


def persist(ctx):
    """Third filter: appends the message as one JSON line to disk.

    LOG_PERSIST_PATH defaults to /data/processed.log, a path expected to
    be a mounted volume so the file survives container restarts.
    """
    path = os.environ.get('LOG_PERSIST_PATH', '/data/processed.log')
    with open(path, 'a') as f:
        f.write(json.dumps(ctx.message) + '\n')
    return ctx


FILTERS = (validate, enrich, persist)


def notify_error(stage_name, error, ctx):
    """Notification filter, only invoked when a stage above raises.

    Sends an email through SendGrid's HTTP API. If SENDGRID_API_KEY or
    SENDGRID_TO are not set, it only logs the failure instead of sending
    anything, so the pipeline keeps working in local and CI environments
    without a SendGrid account configured.
    """
    print('pipeline failed at "{}": {}'.format(stage_name, error))

    api_key = os.environ.get('SENDGRID_API_KEY')
    to_address = os.environ.get('SENDGRID_TO')
    if not api_key or not to_address:
        print('SENDGRID_API_KEY/SENDGRID_TO not set, notify filter is a no-op')
        return

    try:
        requests.post(
            'https://api.sendgrid.com/v3/mail/send',
            headers={
                'Authorization': 'Bearer {}'.format(api_key),
                'Content-Type': 'application/json',
            },
            json={
                'personalizations': [{'to': [{'email': to_address}]}],
                'from': {'email': 'alerts@loopwork.dev'},
                'subject': 'log-message-processor: pipeline failure at {}'.format(stage_name),
                'content': [{
                    'type': 'text/plain',
                    'value': 'Stage: {}\nError: {}\nRaw item: {}'.format(
                        stage_name, error, ctx.raw_item
                    ),
                }],
            },
            timeout=5,
        )
    except requests.RequestException as e:
        print('notify filter itself failed to reach SendGrid: {}'.format(e))
