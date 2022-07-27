# Twitter-Sentiment-AWS-ML-Pipeline <a name="home"></a>
 This project looks at sentiments from Tweets discussing Russian and Ukraine in light of the Russo-Ukrainian conflict. The goal is to get a sense of global public opinion towards Russia and Ukraine. Tweet data is collected, labaled, and analyzed in continuous near-real time. <br><br>
## Table of contents 
 
 1. [<b>Ingestion.</b>](#ingestion) Data is ingested from <b>Twitter's V2 API</b> pushed to <b>S3</b> via <b>Firehose</b> as JSONs,
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

### Key ingestion considerations:
1. <b>Two separate streams.</b> I created two mutually exclusive tweet streams; one for Russia and one for Ukraine. This is in order to get a clear feature for the tweet's topic (either Russia or Ukraine) and to have some confidence that any tweet sentiment is specifically about one topic and about the other or a mix of both. 
1. <b>Exclusion of retweets.</b> In order to avoid applifying the opinions of a few people and to get a more organic representation of public opinion, I decided to omit retweets.
1. <b>Throttling.</b> I throttle the flow of tweets to keep data continuous and manageable within the contrains of Twitter's 2 million filtered streeam monthly cap, to keep storage cost down while keeping a currently representative sample, and to avoid disconnects from overloading the streaming client.
1. <b>Data.</b> I grabbed all available fields that could be used to infer geo data including country codes, user-entered locations, coordinates, and languages. I did not filter for any specific language to keep data as broad a spossible. I also collected additional data not used in the current analysis such as user follower counts, Twitter-generate context annotations, and more. See [raw_tweet_sample.json]() for a sample tweet object.

### Data Dictionary
<details>
<a name="data_dict"></a>
<summary>Show/Hide</summary>
<br>

* <b>id</b>: Unique tweet ID 
* <b>author_id</b>: Unique user ID
    
</details>

### Code
[Link to client twitter_filtered_stream.py](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/1.%20Injestion/twitter_filtered_stream.py)

The following syntax show's how 2 filtering rules are define to accomplish points 1., 2., and 3.
 

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
