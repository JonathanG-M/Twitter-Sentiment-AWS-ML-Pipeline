# Twitter-Sentiment-AWS-ML-Pipeline
 This project looks at sentiments from Tweets discussing Russian and Ukrain in light of the Russo-Ukrainian conflict. The goal is to get a sense of global public opinion towards Russia and Ukraine. <br><br>
 Project architecture: 
 1. <b>Injestion.</b> Data is injested from <b>Twitter's V2 API</b> pushed to <b>S3</b> via <b>Firehose</b> as JSONs,
 1. <b>Transformation.</b> JSONs are batch processed with an <b>AWS Lambda</b>, Tweet are translated to English and sentiments labeled using pre-trained <b>HuggingFace</b> models deployed to <b>SageMaker</b> endpoints, and exported Parquets,
     1. A 2nd EC2 identifies and backfill data missed by step 2. This instance can be activated/deactivated as needed.
 1. <b>Model training</b>. Parquet files are mounted to a <b>Databricks Delta Table</b>, pre-processed using <b>SparkNLP</b>, and use to develop <b>XGBoost</b> models using parallelization and <b>MLFlow</b>.
 1. <b>Insights</b>. The ML enriched data goes from S3 to <b>Quicksight</b> using using <b>Athena</b>. Key ratios are defined using Quicksight's calculated fields and the final data is vizualized through 2 interactive dashboards. 

![Alt text](https://github.com/JonathanG-M/Twitter-Sentiment-AWS-ML-Pipeline/blob/main/img/Twitter%20Sentiment%20Analysis.png)

