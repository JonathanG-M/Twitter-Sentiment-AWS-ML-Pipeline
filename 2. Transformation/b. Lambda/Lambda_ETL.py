# IMPORT modules
from datetime import datetime
import json
import boto3
from io import BytesIO
import os
import awswrangler as wr
import pandas as pd


# CREATE global variables
TRANSLATION_ENDPOINT_NAME = 'hf-translators'
SENTIMENT_ENDPOINT_NAME = 'twitter-sentiment-analyzer'

# INITIALIZE Sagemaker client
sm = boto3.client('runtime.sagemaker')

# INITIALIZE s3 client
s3 = boto3.client('s3')

# INITIALIZE s3 resource
s3_resource = boto3.resource('s3')

def lambda_handler(event, context):
    
    if event:
        
        # CREATE UDF
        def clean_text(text):
            '''
            Cleaning function used in sentiment analysis' Github
            https://github.com/cardiffnlp/timelms/blob/main/scripts/preprocess.py
            '''
            text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
            
            new_text = []
            for t in text.split():
                t = '@user' if t.startswith('@') and len(t) > 1 and t.replace('@','') not in verified_users else t
                new_text.append(t)
            
            return ' '.join(new_text)


        # CREATE UDF
        def translate_tweet(text, lang):
            '''
            Use AWS SageMaker's multi model endpoint to translate non-en tweets
            '''
            # CREATE payload object for Tweet text to translate
            data = {'inputs':text}

            # ENCODE payload
            payload = json.dumps(data).encode()

            # REQUEST payload translation object for specified language (lang)
            response = sm.invoke_endpoint(EndpointName=TRANSLATION_ENDPOINT_NAME,
                                      ContentType='application/json',
                                      Body=payload,
                                      TargetModel = model_dict[lang])

            # EXTRACT translated text
            result = json.loads(response['Body'].read().decode())
            translated_text = result[0]['translation_text']
            
            return translated_text
        
        
        def get_sentiment(text):
            '''
            Use AWS SageMaker's multi model endpoint to tget sentiments
            '''
            # CREATE payload object for sentiment analysis
            data = {'inputs':text}

            # ENCODE payload
            payload = json.dumps(data).encode()

            # REQUEST sentiment score
            response = sm.invoke_endpoint(EndpointName=SENTIMENT_ENDPOINT_NAME,
                          ContentType='application/json',
                          Body=payload)

            # EXTRACT sentiment & score
            result = json.loads(response['Body'].read().decode())
            sentiment, score = result[0]['label'], result[0]['score']
            
            return sentiment, score
        

        # CREATE list of languages to translate. NOTE. This list must match the models from the SageMaker
        # Multi Model Endpoint notebook
        non_en_langs = ['de', 'fr', 'it', 'es', 'ru', 'tr', 'pl', 'ja',
                             'uk',  'tl', 'nl', 'cs', 'da', 'zh',
                             'ar']
        
        # CREATE list of Hugging Face model file names
        model_dict = {lang:f'translator_{lang}_to_en.tar.gz' for lang in non_en_langs}
        
        
        # EXTRACT file path in S3 bucket from AWS Lambda event
        file_obj = event['Records'][0]
        file = file_obj['s3']['object']['key']
        
        # IMPORT file data from S3
        file_data = s3.get_object(Bucket='mydatastash', Key=file)
        
        # DECODE & PARSE file
        file_string = file_data['Body'].read().decode('utf-8')

        # CREATE list of JSONs from new-line delimititer
        file_list = file_string.splitlines()
        
        # INITIALIZE dictionary to hold rows from corresponding languages
        lang_row_dict = {lang : [] for lang in non_en_langs}        
        
        # CREATE list to hold rows from English & translated tweets
        master_list = []
        
        for line in file_list:

            # CREATE dict from JSON
            json_line = json.loads(line)

            # IF tweet language is either English or is in created language list
            if json_line['data']['lang'] == 'en' or json_line['data']['lang'] in non_en_langs:

                # EXTRACT tweet timestamp
                ts = json_line['data']['created_at']

                # EXTRACT tweet id
                tweet_id = json_line['data']['id']

                # EXTRACT tweet author id
                author_id = json_line['data']['author_id']

                # EXTRACT tweet text
                text = json_line['data']['text']

                # EXTRACT tweet language
                lang = json_line['data']['lang']
                
                # IF places object exists on tweet
                if 'places' in json_line['includes']:

                    # EXTRACT country code
                    country_code = json_line['includes']['places'][0]['country_code']
                    
                else:

                    # CREATE blank country code
                    country_code = ''


                # IF tweet has location
                if 'location' in json_line['includes']['users'][0]:

                    # EXTRACT location
                    location = json_line['includes']['users'][0]['location']

                else:

                    # CREATE blank location
                    location = ''


                 # EXTRACT rule tag. NOTE: See twitter sentiment streaming client filter rule creation.
                tag = json_line['matching_rules'][0]['tag']
            
                # CREATE list from extracted tweet elements
                tweet = [ts, tweet_id, author_id, text, lang, country_code, location, tag]

                # APPPEND list to master list
                master_list.append(tweet)
    
    
    # CREATE column names
    cols = ['ts', 'tweet_id', 'author_id', 'text', 'lang', 'country_code', 'location', 'tag']
    
    # CREATE dataframe
    df = pd.DataFrame(master_list, columns = cols)
    
    # CAST int columns
    df['tweet_id'] = df['tweet_id'].astype('int64')
    df['author_id'] = df['author_id'].astype('int64')
    df['ts'] = pd.to_datetime(df['ts'], utc=True).dt.tz_convert(None) # change iso timestamp to datetime
    
    # REPLACE links with 'http'. NOTE. This is as per HF model author recommendations.
    # EDIT: 'http' was giving weird results so changed to blank
    df['text'] = df['text'].replace(r'http\S+', '', regex=True)
    
    
    # REQUEST TRANSLATED TWEETS FROM SAGEMAKER ENDPOINTS
    df['translated_text'] = df.apply(lambda x: x['text'] if x['lang'] == 'en' else  translate_tweet(x['text'], x['lang']), axis=1)
    
    
    # IMPORT verified users from S3. NOTE. This is as per HF model author recommendations.
    verified_users = s3.get_object(Bucket='mydatastash', Key='support_data/approved_users.txt')
    verified_users = verified_users['Body'].read().decode('utf-8').splitlines()    
    
    # Preprocess before sentiment analysis
    # NOTE. this step needs fixing beause the translation translates certain handles,
    #       so need to figure out a way to either mask or substitute handles prior to
    #       translation. (Or just use a multi-lang sentiment analysis model ¯\_(ツ)_/¯)
    # Replace non-veried users by @User (as per hf model author recommendations)
    df['translated_text'] = df['translated_text'].apply(clean_text)
    
    
    # REQUEST SENTIMENT SCORES FROM SAGEMAKER ENDPOINT
    sentiment_tuples = df['translated_text'].apply(get_sentiment)
    df['sentiment'], df['score'] = [tup[0] for tup in sentiment_tuples], [float(tup[1]) for tup in sentiment_tuples]

    # CREATE export S3 bucket name from existing S3 bucket
    EXPORT_BUCKET_NAME = 'lambda-epl-output'
    EPL_PREFIX = 'twitter_stream'
    
    # CREATE export path structure to match the path structure of the incoming S3 bucket file location
    # SPLIT file path from AWS Lambda object path
    path_list = file.split('/')

    # EXTRACT year
    year = path_list[1]

    # EXTRACT month
    month = path_list[2]

    # EXTRACT day
    day = path_list[3]

    # EXTRACT hour
    hour = path_list[4]

    # CREATE timestamp
    now = datetime.utcnow()
    timestamp = int(now.timestamp() * 100000)

    # CREATE file name
    file_name = f'tweets{timestamp}.parquet'
    
    # CREATE export file path
    file_key = os.path.join('s3://',EXPORT_BUCKET_NAME,EPL_PREFIX, year, month, day, hour, file_name)    
    
    # EXPORT as Parquet to export file path
    wr.s3.to_parquet(
        df=df,
        path=file_key)
    
    
    return "Done!"
    
    
    