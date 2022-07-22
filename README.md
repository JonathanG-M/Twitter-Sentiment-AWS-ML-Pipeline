# Twitter-Sentiment-AWS-ML-Pipeline
 This project looks at sentiments from Tweets discussing Russian and Ukrain in light of the Russo-Ukrainian conflict. The goal is to get a sense of global public opinion towards Russia and Ukraine. <br><br>
 The pipeline's architecture looks something like this: 
 1. Data is injested from Twitter's V2 API using a client hosted on EC2 and pushed to S3 via Firehose as JSONs,
 1. JSONs are batch processed with Lambda & SageMaker ML endpoint, and exported to another S3 bucket as Parquets,
     1. A 2nd EC2 instance is configured to backfill data missed by step 2. due to downtime, and issues with the SageMaker endpoint. This instance can be activated/deactivated as needed.
 1. 

  and visualized using Quicksight.

![Alt text](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/img/Twitter%20Sentiment%20Analysis.png)

