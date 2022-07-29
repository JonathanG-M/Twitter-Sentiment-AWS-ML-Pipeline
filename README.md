# Twitter-Sentiment-AWS-ML-Pipeline <a name="home"></a>
 This project looks at sentiments from Tweets discussing Russian and Ukraine in light of the Russo-Ukrainian conflict. The goal is to get a sense of global public opinion towards Russia and Ukraine over time and by region, language, etc. Tweet data is collected, labeled, and analyzed in continuous near-real time. <br><br>
## Table of contents 
 
 1. [<b>Ingestion.</b>](#ingestion) Data is ingested from <b>Twitter's V2 API</b> pushed to <b>S3</b> via <b>Firehose</b> as JSONs,
    1. [Key ingestion considerations](#key_ingestion_considerations)
    1. [Data Dictionary](#ingestion_data_dict)
    1. [Code](#ingestion_code)
 1. [<b>Transformation.</b>](#transformation) JSONs are batch processed with an <b>AWS Lambda</b>, Tweet are translated to English and sentiments labeled using pre-trained <b>HuggingFace</b> models deployed to <b>SageMaker</b> endpoints, and exported Parquets,
   1. [<b>Backfilling.</b>](#transformation) A 2nd EC2 identifies and backfill data missed by step 2. This instance can be activated/deactivated as needed.
 1. [<b>Model training</b>.](#training) Parquet files are mounted to a <b>Databricks Delta Table</b>, pre-processed using <b>SparkNLP</b>, and use to develop <b>XGBoost</b> models using parallelization and <b>MLFlow</b>.
 1. [<b>Insights</b>.](#insights) The ML enriched data goes from S3 to <b>Quicksight</b> using using <b>Athena</b>. Key ratios are defined using Quicksight's calculated fields and the final data is vizualized through 2 interactive dashboards. 
<br>

![Alt text](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/img/Twitter%20Sentiment%20Analysis.png)
<i> Figure. Overview of project processes and resources.</i>

<br><br>
## Ingestion
<a name="ingestion"></a>
[<u>Back to top</u>](#home)
<br>

### Key ingestion considerations<a name="key_ingestion_considerations"></a>

1. <b>Two separate streams.</b> I created two mutually exclusive tweet streams; one for Russia and one for Ukraine. This is in order to get a clear feature for the tweet's topic (either Russia or Ukraine) and to have some confidence that any tweet sentiment is specifically about one topic and about the other or a mix of both. 
1. <b>Exclusion of retweets.</b> In order to avoid applifying the opinions of a few people and to get a more organic representation of public opinion, I decided to omit retweets.
1. <b>Throttling.</b> I throttle the flow of tweets to keep data continuous and manageable within the contrains of Twitter's 2 million filtered streeam monthly cap, to keep storage cost down while keeping a currently representative sample, and to avoid disconnects from overloading the streaming client.
1. <b>Data.</b> I grabbed all available fields that could be used to infer geo data including country codes, user-entered locations, coordinates, and languages. I did not filter for any specific language to keep data as broad a spossible. I also collected additional data not used in the current analysis such as user follower counts, Twitter-generate context annotations, and more. 

### Data Dictionary<a name="ingestion_data_dict"></a>


See [raw_tweet_sample.json](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/1.%20Ingestion/sample/raw_tweet_sample.json) for a sample tweet object.
<details>
<summary>Show/Hide data dictionary</summary>
<br>

* <b>data</b>: Tweet data object
* <b>data > author_id</b>: Unique user ID 
* <b>data > context_annotation</b>: Twitter's own named entity recognition
* <b>data > created_at</b>: Tweet creation date
* <b>data > geo > place_id</b>: Tweet-specific location id. Location data can be found in <b>data > includes > places</b> 
* <b>data > id</b>: Tweet unique id
* <b>data > lang</b>: Language detected by Twitter
* <b>data > text</b>: The actual Tweet text
* <b>data > includes</b>: Expansion of people data and place data mentioned in data > text and data > geo
* <b>data > includes > users</b>: User data, including the tweet's author.
* <b>data > includes > users[i] > location</b>: Location data manually entered by user. Low reliability since users can enter anything (USA, Atlantis, Mom's basemend, etc.)
* <b>data > includes > users[i] > name</b>: User's screen name. Not unique.
* <b>data > includes > users[i] > pubic metrics</b>: High-level user stats (followers, tweet count, etc)
* <b>data > includes > users[i] > username</b>: User's unique @ twitter handle
* <b>matching_rules</b> Filtered stream rule which this tweet matches on
* <b>matching_rules > tag</b> Optional tag which can be set to use as a feature. This is how data is tagged in point 1. under [key ingestion considerations](#key_ingestion_considerations)
    
</details>

### Code<a name="ingestion_code"></a> 
[Link to client twitter_filtered_stream.py](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/1.%20Ingestion/twitter_filtered_stream.py)

The following syntax show's how 2 filtering rules are define to accomplish points 1. two separate streams, 2. exclusion of retweets, and 3. throttling:

![Alt Text](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/img/filtering_rules.png)
<i> Figure. Screenshot of filtered stream rules.</i><br><br>

The following syntax how the tweet object's contents are requested from the Twitter API:
![Alt Text](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/img/tweet_object_rules.png)


<br><br>
## Transformation
<a name="transformation"></a>
[<u>Back to top</u>](#home)
<br>

### Key tranformation considerations<a name="key_transformation_considerations"></a>

1. <b>Schedule.</b> The transformation script runs every 5 minutes when Firehose generates a new file and triggers an event in Lambda.
1. <b>Translation.</b> Tweet texts are translated into English from 15 other languages using a pre-trained translation models from the Hugging Face Hub and loaded into a SageMaker endpoint. See my [SageMaker notebook](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/2.%20Transformation/a.%20Sagemaker%20notebooks/translator_mme_deploy.ipynb) for translation endpoint details.
1. <b>Sentiment labeling.</b> English and translated are labeled as positive, neutral, or negative using a pre-trained sentiment analysis model from the Hugging Fave Hub and loaded into a SageMaker endpoint. See my [SageMaker notebook](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/2.%20Transformation/a.%20Sagemaker%20notebooks/hf_sentiment_model_deploy.ipynb) for sentiment analysis endpoint details.
1. <b>Data.</b> 11 columns are outputed in Parquet format. These include tweet and user identifiers, translated and raw tweets, sentiment scores, as well as language and geo data for analyses. See the [data dictionary](#transformation_data_dict) below for full field details.
1. <b>Backfilling.</b> A second script identifies and processes data missed by the Lambda transformation following the above considerations. The backfill script can be found [here](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/2.%20Transformation/c.%20EC2%20backfill/twitter_backfill_client.py), and the supporting Athena script can be found [here](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/2.%20Transformation/c.%20EC2%20backfill/get_processed_files.sql).


### Data Dictionary<a name="transformation_data_dict"></a>

See [parquet_sample_file.csv](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/2.%20Transformation/sample/parquet_sample_file.csv) for a sample of the labeled output. (Note. The sample is in CSV format for viewing purposes)
<details>
<summary>Show/Hide data dictionary</summary>
<br>

* <b>ts</b>: Timestamp of the tweet's creation
* <b>tweet_id</b>: Tweet unique id
* <b>author_id</b>: Author unique id
* <b>text</b>: The actual Tweet text
* <b>lang</b>: Language detected by Twitter
* <b>country_code</b>: ISO country code for users sharing location
* <b>location</b>: Location data manually entered by user. Low reliability since users can enter anything (USA, Atlantis, Mom's basemend, etc.)
* <b>tag</b>: Tag of matching filtering rules to use as a feature. This is how data is tagged in point 1. under [key ingestion considerations](#key_ingestion_considerations)
* <b>translated_text</b>: Translated tweet text
* <b>sentiment</b>: Sentiment polarity labeled as either Positive, Neutral, or Negative
* <b>score</b>: Sentiment score with greater values indicating greater confidence in the sentiment label
    
</details>

### Code<a name="transformation_code"></a> 
[Link to client Lambda_ETL.py](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/2.%20Transformation/b.%20Lambda/Lambda_ETL.py)

The two key steps in the transformation; translation and sentiment analysis:

<b>Translation using SageMaker endpoint</b>

```python
# INITIALIZE Sagemaker client
sm = boto3.client('runtime.sagemaker')

# CREATE UDF for translation
def translate_tweet(text, lang):

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
    
# REQUEST TRANSLATED TWEETS FROM SAGEMAKER ENDPOINTS
df['translated_text'] = df.apply(lambda x: x['text'] if x['lang'] == 'en' else  translate_tweet(x['text'], x['lang']), axis=1)  
```

<b>Sentiment labeling using SageMaker endpoint</b>

```python
# INITIALIZE Sagemaker client
sm = boto3.client('runtime.sagemaker')

# CREATE UDF for sentiment scoring
def get_sentiment(text):

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

# REQUEST SENTIMENT SCORES FROM SAGEMAKER ENDPOINT
sentiment_tuples = df['translated_text'].apply(get_sentiment)
df['sentiment'], df['score'] = [tup[0] for tup in sentiment_tuples], [float(tup[1]) for tup in sentiment_tuples]
```


<br><br>
## Model Training
<a name="training"></a>
[<u>Back to top</u>](#home)
<br>

* Something else
<br><br>
## Insights
<a name="insights"></a>
[<u>Back to top</u>](#home)
<br>

* Something else
