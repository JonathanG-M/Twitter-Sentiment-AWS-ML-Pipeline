import requests
import os
import json
import boto3
import time
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# To create bearer token variable in local envirnment. Run this in terminal:
# export 'BEARER_TOKEN'='<your_bearer_token>'

# Verify that it worked with:
# bearer_token = os.environ.get("BEARER_TOKEN")



# CREATE UDF: get bearer token from AWS' secrets manager
def get_bearer_token():

    # INITIALIZE simple system manager instance
    ssm = boto3.client('ssm', 'ca-central-1')

    # IMPORT bearer token JSON object
    my_token_dict = ssm.get_parameters(
        Names=['BEARER_TOKEN_PROD'], WithDecryption=True)

    # EXTRACT bearer token
    my_token = my_token_dict['Parameters'][0]['Value']

    return my_token

# CREATE UDF: create Requests session with reconnect backoff logic
def retry_session(retries, session=None, backoff_factor=0.3):
    
    # INITIALIZE Session object
    session = session or requests.Session()
    
    # INTIALIZE Retry object
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        allowed_methods=False,
    )

    # INITIALIZE HTTP Adapter
    adapter = HTTPAdapter(max_retries=retry)

    # ADD adapter to session http scenarios
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    return session


# CREATE UDF: initialize AWS logs client
def get_log_client():
    log_client = boto3.client('logs')
    return log_client

# CREATE UDF: get sequence token from AWS logs client
def get_seq_token(log_client):

    # IMPORT log stream description JSON
    response = log_client.describe_log_streams(logGroupName='twitter-stream-logs', logStreamNamePrefix='primary')
    
    # EXTRACT sequence token from JSON
    token = response['logStreams'][0]['uploadSequenceToken']

    return token


def bearer_oauth(r):
    """
    Method required by bearer token authentication.
    """
    my_token = get_parameters()
    r.headers["Authorization"] = f"Bearer {my_token}"
    r.headers["User-Agent"] = "v2FilteredStreamPython"
    return r


# CREATE UDF: get existing filter rules from Twitter Stream instance
def get_rules():
    '''
    Function gets list of existing filtering rules and filtering rule ID.
    '''

    # IMPORT rules
    response = requests.get(
        "https://api.twitter.com/2/tweets/search/stream/rules", auth=bearer_oauth
    )

    if response.status_code != 200:
        raise Exception(
            "Cannot get rules (HTTP {}): {}".format(response.status_code, response.text)
        )
    print(json.dumps(response.json()))
    return response.json()

# CREATE UDF: delete existing rules while initializing the current stream
def delete_all_rules(rules):

    # CHECK if rules exist
    if rules is None or 'data' not in rules:
        return None

    # CREATE list of rule IDs
    ids = list(map(lambda rule: rule["id"], rules['data']))

    # CREATE dictionary for API payload containing rule IDs
    payload = {"delete": {"ids": ids}}

    # POST request to API to delete rules
    response = requests.post(
        "https://api.twitter.com/2/tweets/search/stream/rules",
        auth=bearer_oauth,
        json=payload
    )
    if response.status_code != 200:
        raise Exception(
            "Cannot delete rules (HTTP {}): {}".format(
                response.status_code, response.text
            )
        )
    print(json.dumps(response.json()))

# CREATE UDF: create rules
def set_rules(delete):
    # CREATE rules. 
    # Rules can be adjusted manually here. Review Twitter V2 API documents for rule syntax.
    rules = [{'value': '(ukraine OR ukraina OR Украина OR україни OR zelenski) '
                       '-russia -rossiya -Россия -russie -Росія -putin '
                       '-is:retweet sample:10',
             'tag': 'ukraine'},
            {'value': '(russia OR rossiya OR Россия OR russie  OR putin) '
                      '-ukraine -ukraina -Украина -україни -zelenski '
                      '-is:retweet sample:10',
             'tag': 'russia'}]
    
    # CREATE dictionary with rules API payload
    payload = {"add": rules}

    # POST rules to Twitter API
    response = requests.post(
        "https://api.twitter.com/2/tweets/search/stream/rules",
        auth=bearer_oauth,
        json=payload,
    )

    if response.status_code != 201:
        raise Exception(
            "Cannot add rules (HTTP {}): {}".format(response.status_code, response.text)
        )
    print(json.dumps(response.json()))


# CREATE UDF: create Twitter V2 Stream instance.
def get_stream(set, log_client):

    # CREATE tweet fields object. This specifies the Twwet object fields we want Twitter API to give us.
    tweet_fields = r'tweet.fields=id,text,created_at,lang,context_annotations' \
                   '&expansions=author_id,geo.place_id' \
                   '&place.fields=id,country_code' \
                   '&user.fields=id,name,username,public_metrics,location'

    # INITIALIZE custom retry session object
    sess = retry_session(retries=10, backoff_factor=2)

    # REQUEST strean fron Twitter API
    response = sess.get(
        "https://api.twitter.com/2/tweets/search/stream?{tweet_fields}".format(tweet_fields=tweet_fields),
        auth=bearer_oauth,
        stream=True)

    print(response.status_code)

    # CHECK if error
    if response.status_code != 200:

        # IF error INITIALIZE AWS log client 
        seq_token = get_seq_token(log_client)

        # CREATE payloadf dictionary with error code
        log_event = {'logGroupName': 'twitter-stream-logs',
                     'logStreamName': 'primary',
                     'sequenceToken': seq_token,
                     'logEvents':
                         [{'timestamp': int(round(time.time() * 1000,0)),
                           'message': "Cannot get stream (HTTP {}): {}".format(response.status_code, response.text)}]
                     }
        
        # POST error code to AWS logs & raise exception
        log_response = log_client.put_log_events(**log_event)
        raise Exception("Cannot get stream (HTTP {}): {}".format(response.status_code, response.text))

    else:
        # If connection is successful, reset reconnection retries to 0
        global retries
        retries = 0

    # STREAM data using .iter_lines() method
    for response_line in response.iter_lines():
        if response_line:

            # CHECK API payload for server-side error messages. Delivery to AWS logs & raise exception if any
            if 'errors' in json.loads(response_line):
                response = json.loads(response_line)
                seq_token = get_seq_token(log_client)
                log_event = {'logGroupName': 'twitter-stream-logs',
                             'logStreamName': 'primary',
                             'sequenceToken': seq_token,
                             'logEvents':
                                 [{'timestamp': int(round(time.time() * 1000, 0)),
                                   'message': response_line.decode('utf-8') } ] }
                log_response = log_client.put_log_events(**log_event)
                raise Exception(response['errors'])

            # ON tweet response
            else:
                # APPEND newline (in bytes) to Tweet JSON object
                response_line = response_line + b'\n'

                # PUSH JSON object through AWS firehose
                firehose_client.put_record(DeliveryStreamName=delivery_stream_name, Record={'Data': response_line})


# CREATE global variable for retry count in reconnect backoff factor
RETRIES = 0

def main():
    log_client = get_log_client()
    rules = get_rules()
    delete = delete_all_rules(rules)
    set = set_rules(delete)

    # Set up reconnection parameters
    retry =True
    backoff_factor = 2
    global retries
    RETRIES = 0
    max_retries = 10

    while retry == True:

        try:
            get_stream(set, log_client)

        except KeyboardInterrupt:
            raise KeyboardInterrupt

        except:

            time_delay = backoff_factor * (2 ** (retries - 1))
            print(f'Connection failed. Retrying to connect in {time_delay} seconds...')

            time.sleep(time_delay)

            if retries == max_retries:
                raise Exception(response['errors'])

            retries +=1





if __name__ == "__main__":
    # get bearer token from AWS SSM
    #    my_token = get_parameters('BEARER_TOKEN')
    # create kinesis client connection
    session = boto3.Session()

    # Create client for logging error
    log_client = get_log_client()

    # create the kinesis firehose client
    firehose_client = session.client('firehose', region_name='ca-central-1')

    # Set kinesis data stream name
    delivery_stream_name = 'twitter'

    main()
