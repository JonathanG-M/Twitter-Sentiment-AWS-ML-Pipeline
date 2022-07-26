import boto3
import awswrangler as wr
import pandas as pd
import json
from datetime import datetime
import time
import gzip
from transformers import pipeline


# CREATE global variables
TRANSLATION_ENDPOINT_NAME = 'hf-translators'
SENTIMENT_ENDPOINT_NAME = 'twitter-sentiment-analyzer'
sm = boto3.client('runtime.sagemaker', region_name = 'ca-central-1')

# INITIALIZE boto3
session = boto3.Session()

# INITIALIZE S3 resource
s3 = session.resource('s3')

# INTIALIZE S3 client
s3_client = session.client('s3')

# INITIALIZE bucket resource instance
my_bucket = s3.Bucket('mydatastash')

# INITIALIZE AWS logs client
log_client = boto3.client('logs', region_name='ca-central-1')

# CREATE list of languages to translate. NOTE. This list must match the models from the SageMaker
non_en_langs = ['de', 'fr', 'it', 'es', 'ru', 'tr', 'pl', 'ja', 'uk', 'tl', 'nl', 'cs', 'da', 'zh', 'ar']
dest_lang = 'en'

# CREATE list of Hugging Face model file names
model_dict = {lang : pipeline(model=f'Helsinki-NLP/opus-mt-{lang}-{dest_lang}') for lang in non_en_langs}


# CREATE sentiment model path
model_path = r'cardiffnlp/twitter-roberta-base-sentiment-latest'

# IMPORT sentiment model from HF hub
sentiment_pipeline = pipeline('sentiment-analysis', model=model_path, tokenizer=model_path)



# CREATE UDF
def get_seq_token(log_client):
    response = log_client.describe_log_streams(logGroupName='twitter-stream-logs', logStreamNamePrefix='backfill-job')
    token = response['logStreams'][0]['uploadSequenceToken']
    return token

# CREATE UDF
def clean_text(text):
    '''
    Cleaning function used in sentiment analysis' Github
    https://github.com/cardiffnlp/timelms/blob/main/scripts/preprocess.py
    '''
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')

    new_text = []
    for t in text.split():
        t = '@user' if t.startswith('@') and len(t) > 1 and t.replace('@', '') not in verified_users else t
        new_text.append(t)

    return ' '.join(new_text)

# CREATE UDF
def translate_tweet(text, lang):
    '''
    Use local model to translate non-en tweets
    '''
    result = model_dict[lang](text)
    translated_text = result[0]['translation_text']
    return translated_text


# CREATE UDF
def get_sentiment(text):
    '''
    Use local model to get sentiment scoring
    '''
    response = sentiment_pipeline(text)
    sentiment, score = response[0]['label'], response[0]['score']

    return sentiment, score



# IMPORT verified users
verified_users = s3_client.get_object(Bucket='mydatastash', Key='support_data/approved_users.txt')
verified_users = verified_users['Body'].read().decode('utf-8').splitlines()


# IMPORT list of files UNLOADED via athena query. NOTE. This list includes files PROCESSED by Lambda ETL client
keys = []

# IMPORT Processed files.
for file in my_bucket.objects.filter(Prefix='athena-twitter-stream/existing'):
    keys.append(file.key)

# CREATE list for imported file names
processed_files = []

# EXTRACT file names from processed files
for key in keys:
    obj = s3_client.get_object(Bucket='mydatastash', Key=key)
    with gzip.GzipFile(fileobj=obj['Body']) as gzipfile:
        content = gzipfile.read().decode()
    files_file = content.splitlines()
    processed_files = processed_files + files_file

# SUBSTRING drop bucket name from file paths
processed_files = [x[17:] for x in processed_files]


# Get all files from my main twitter streaming data store
# Initiate blank string object
str_obj = ''

# Iterate through all sub directories in mydatastash/twitter_stream/ and get the file names
paginator = s3_client.get_paginator('list_objects')
operation_parameters = {'Bucket': 'mydatastash',
                        'Prefix': 'twitter_stream'}
# Create iterator
page_iterator = paginator.paginate(**operation_parameters)

# Get all file names and append new line character
for page in page_iterator:
    for content in page['Contents']:
        str_obj = str_obj + content['Key'] + '\n'
# Split string into list by new line character
all_files = str_obj.splitlines()

# We don't want to process file create on or after the 28th since that's when I did the Athena pull. We can do another
#   Athena pull after to see if more files are missing.
all_files = [x for x in all_files if int(x.split('/')[3]) < 50]

# Check all_files and save files that are not in the processed_files list.
unprocessed_files = [x for x in all_files if x not in processed_files]



# Process data and export
for file in unprocessed_files[::-1]:

    now = datetime.utcnow()
    print(f'Processing file {file} at {now}')

    try:
        # Get file data
        file_data = s3_client.get_object(Bucket='mydatastash', Key=file)

        # read and decode file data
        file_string = file_data['Body'].read().decode('utf-8')
        # Split file by new line character into a list of string JSON objects
        file_list = file_string.splitlines()

        # List to append individual line elements
        master_list = []

        # Iterate through each JSON in the file and extract desired elements
        for line in file_list:
            json_line = json.loads(line)

            if json_line['data']['lang'] == 'en' or json_line['data']['lang'] in non_en_langs:
                # If Tweet language is English
                ts = json_line['data']['created_at']
                tweet_id = json_line['data']['id']
                author_id = json_line['data']['author_id']
                text = json_line['data']['text']
                lang = json_line['data']['lang']

                # Check if place exists, get country code if it does
                if 'places' in json_line['includes']:
                    country_code = json_line['includes']['places'][0]['country_code']

                else:
                    # Otherwise leave it blank for now. Will try to get this later
                    country_code = ''

                # Check if user has a custom place in user object and grab it if they do
                if 'location' in json_line['includes']['users'][0]:
                    location = json_line['includes']['users'][0]['location']
                else:
                    location = ''

                # Add the tweet matching rule tag
                tag = json_line['matching_rules'][0]['tag']

                # Add elements to tweet list
                tweet = [ts, tweet_id, author_id, text, lang, country_code, location, tag]
                # Append tweet list to master list
                master_list.append(tweet)

        cols = ['ts', 'tweet_id', 'author_id', 'text', 'lang', 'country_code', 'location', 'tag']
        # Convert master_list to dataframe
        df = pd.DataFrame(master_list, columns=cols)

        # Change column types
        df['tweet_id'] = df['tweet_id'].astype('int64')
        df['author_id'] = df['author_id'].astype('int64')
        df['ts'] = pd.to_datetime(df['ts'], utc=True).dt.tz_convert(None)  # change iso timestamp to datetime

        # Replace links with 'http' as per model author recommendations
        df['text'] = df['text'].replace(r'http\S+', 'http', regex=True)
        df['text'] = df['text'].replace(r'\n', ' ', regex=True)
        # ------------------------TRANSLATE NON EN TWEET FROM SAGEMAKER ENDPOINT-------------------------------------
        df['translated_text'] = df.apply(lambda x: x['text'] if x['lang'] == 'en' else  translate_tweet(x['text'], x['lang']), axis=1)

        # Clean string
        df['text'] = df['text'].apply(clean_text)

        # -------------------------SENTIMENT ANALYSIS FROM SAGEMAKER ENDPOINT--------------------------------------
        sentiment_tuples = df['translated_text'].apply(get_sentiment)
        df['sentiment'], df['score'] = [tup[0] for tup in sentiment_tuples], [float(tup[1]) for tup in sentiment_tuples]

        # get the files elements
        date_elements = file.split('/')
        specifics = date_elements[-1].split('-')

        # get output file path TEST
        EXPORT_BUCKET = 'lambda-epl-output-test'
        file_folder = date_elements[0]
        file_year = date_elements[1]
        file_month = date_elements[2]
        file_day = date_elements[3]
        file_hour = date_elements[4]
        file_minute = specifics[6]

        # Get timestamp now
        now = datetime.utcnow()
        ts_now = int(now.timestamp() * 100000)

        # File name
        file_name = f'tweets_{file_minute}_{ts_now}.parquet'

        # create export key
        path_list = ['s3:/', EXPORT_BUCKET, file_folder, file_year, file_month, file_day, file_hour, file_name]

        file_key = '/'.join(path_list)

        # Export to S3 as parquet
        wr.s3.to_parquet(df=df,
                         path=file_key,
                         boto3_session=session)

        print(f'PROCESSED file {file} at {now} and saved to {file_key}')

    except Exception as e:

        log_event = {'logGroupName': 'twitter-stream-logs',
                     'logStreamName': 'backfill-job',
                     'logEvents':
                         [{'timestamp': int(round(time.time() * 1000,0)),
                           'message': f'Encountered exception {e} while processing file {file}'}]}

        event_str = log_event['logEvents']
        print(f'ERROR encountered: {event_str}')

        pass
