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
[Back to top](#home)
1. <b>Two separate streams.</b> I created two mutually exclusive tweet streams; one for Russia and one for Ukraine. This is in order to get a clear feature for the tweet's topic (either Russia or Ukraine) and to have some confidence that any tweet sentiment is specifically about one topic and about the other or a mix of both. 
1. <b>Exclusion of retweets.</b> In order to avoid applifying the opinions of a few people and to get a more organic representation of public opinion, I decided to omit retweets.
1. <b>Throttling.</b> I throttle the flow of tweets to keep data continuous and manageable within the contrains of Twitter's 2 million filtered streeam monthly cap, to keep storage cost down while keeping a currently representative sample, and to avoid disconnects from overloading the streaming client.
1. <b>Data.</b> I grabbed all available fields that could be used to infer geo data including country codes, user-entered locations, coordinates, and languages. I did not filter for any specific language to keep data as broad a spossible. I also collected additional data not used in the current analysis such as user follower counts, Twitter-generate context annotations, and more. 

### Data Dictionary<a name="ingestion_data_dict"></a>
[Back to top](#home)

See [raw_tweet_sample.json](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/1.%20Ingestion/sample/raw_tweet_sample.json) for a sample tweet object.
<details>
<summary>Show/Hide data dictionary</summary>
<br>

* <b>data</b>: Tweet data 
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

* Something else
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
