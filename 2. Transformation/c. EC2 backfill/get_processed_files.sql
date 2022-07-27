/* Script description
This script extracts the file paths from file that have been processed, and joins them back to the unprocessed files 
by joining on the tweet ID. 

Dump the data in an S3 bucket as a CSV.
*/

UNLOAD (SELECT DISTINCT(path)                           # Select file path
        FROM twitter.labeled_twitter_stream lts
        JOIN    (SELECT data.id, "$path" AS path        # Inner join processed and unprocessed files to filter 
                FROM twitter.twitter_stream) ts
            ON ts.id = CAST(lts.tweet_id AS VARCHAR)
        )
TO 's3://mydatastash/athena-twitter-stream/existing/'   # Dump top this bucket
WITH (format = 'TEXTFILE', field_delimiter  = ',')      # As CSV
;