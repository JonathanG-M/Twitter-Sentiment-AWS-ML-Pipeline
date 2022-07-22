# Twitter-Sentiment-AWS-ML-Pipeline
 This project looks at sentiments from Tweets discussing Russian and Ukrain in light of the Russo-Ukrainian conflict. The goal is to get a sense of global public opinion towards Russia and Ukraine. <br><br>
 The pipeline's architecture looks something like this: 
 1. Injestion. Data is injested from Twitter's V2 API using a client hosted on EC2 and pushed to S3 via Firehose as JSONs,
 1. Transformation. JSONs are batch processed with an AWS Lambda, Tweet texts are translated to English, sentiments are labeled as positive, negative, and neutral using pre-trained HuggingFace transformers deployed to SageMaker endpoints, and exported to another S3 bucket as Parquets,
     1. A 2nd EC2 instance is configured to identify and backfill data missed by step 2. due to downtime, and issues with the SageMaker endpoint. This instance can be activated/deactivated as needed.
 1. Model training. Parquet files are mounted to a Databricks Delta Table, pre-processed using SparkNLP, and use to train XGBoost models using parallelization and MLFlow.
 1. Insights. The ML enriched data goes from S3 to Quicksight using using AWS Glue and Athena. Key ratios are defined using Quicksight's calculated fields and the final data is vizualized through 2 interactive dashboards. 

![Alt text](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/img/Twitter%20Sentiment%20Analysis.png)

