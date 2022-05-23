# -*- coding: utf-8 -*-
"""coherent version of A2.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/12wDHgk3SLKJT24j4wsS35O-BscbEL5zy
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql import Window, Row
from pyspark.sql.types import IntegerType, StringType, FloatType

def split_true_context(line):
  stride = 2048
  window_size = 4096
  # stride = 256
  # window_size = 512
  result = []
  source_number = int(line[5])
  context_length = len(line[1])
  if(context_length % stride ==0):
    times = context_length / stride
  else:
    times = int(context_length / stride) + 1
  if(source_number ==0):
    return []
  else:
    for i in range(times):
      result.append(Row(source=line[1][i * stride: i * stride + window_size], question=line[0], answer_start=0, answer_end=0))
      #result.append((line[0][i * stride: i * stride + window_size], line[2], 0, 0, "impossible negative", line[5]))
    return result[:source_number]


def split_false_context(line):
    stride = 2048
    window_size = 4096
    # stride = 256
    # window_size = 512
    result = []
    context_length = len(line[0])
    if(context_length % stride ==0):
      times = context_length / stride
    else:
      times = int(context_length / stride) + 1
    if times==1:
      return []
    else:
      count = 0
      temp_result = []
      for i in range(times):
        answer_start_of_contract = line[3]
        answer_end_of_contract = line[3] + len(line[4])
        if(i* stride <= answer_start_of_contract < i * stride + window_size or i* stride < answer_start_of_contract <= i * stride + window_size):
          result.append(Row(source=line[0][i * stride: i * stride + window_size], question=line[2], answer_start=line[3] % stride, answer_end=line[3] % stride + len(line[4]), type_name="positive"))
          #result.append((line[0][i * stride: i * stride + window_size], line[2], line[3] % stride, line[3] % 2048 + len(line[4]), "positive", line[5]))
          count += 1
        else:
          temp_result.append(Row(source=line[0][i * stride: i * stride + window_size], question=line[2], answer_start=0, answer_end=0, type_name="possible nagative"))
          #temp_result.append((line[0][i * stride: i * stride + window_size], line[2], 0, 0, "possible negative", line[5]))
      if count==1:
        result.append(temp_result[0])
      else:
        result.extend(temp_result[:count])
      return result


def impossible_count(count, positive_contract_count):
  result = float(count / positive_contract_count)
  return result

spark = SparkSession \
    .builder \
    .appName("COMP5349 A2") \
    .config("spark.driver.memory", "10g")\
    .config("spark.sql.inMemoryColumnarStorage.compressed", "true")\
    .config("spark.sql.execution.arrow.enabled", "true")\
    .getOrCreate() 

data = "test.json"
data = "CUADv1.json"
data = "train_separate_questions.json"
init_df = spark.read.json(data)
data_df = init_df.select(explode("data").alias("data"))
paragraph_df = data_df.select(explode("data.paragraphs").alias("paragraph"))


context_qas_df = paragraph_df.select("paragraph.context", explode("paragraph.qas").alias('qas'))

positive_contract_number = context_qas_df.where(col("qas.is_impossible")== False).groupBy("context").count().withColumnRenamed("count","positive_contract_count")

temp_df = context_qas_df.select("context", "qas.is_impossible", "qas.question", explode_outer("qas.answers").alias('answers'))
element_df = temp_df.select("context", "is_impossible", "question", "answers.answer_start", "answers.text").cache()
element_rdd = element_df.where(col("is_impossible") == False).rdd.map(lambda x:(x[0], x[1], x[2], x[3], x[4])).cache()
type_rdd = element_rdd.flatMap(split_false_context)
type_df = spark.createDataFrame(type_rdd).cache()

positive_possible_result = type_df.select("source","question","answer_start","answer_end")
positive_count = type_df.where(col("type_name")=="positive").groupBy("question").count()

impossible_df = element_df.where(col("is_impossible") == True).join(positive_count,"question",'inner').join(positive_contract_number,"context",'inner').cache()
udf_fc = udf(lambda x,y:impossible_count(x,y), FloatType())
impossible_df = impossible_df.withColumn("impossible_count",udf_fc(col("count"),col("positive_contract_count"))).select("*",round("impossible_count")).withColumnRenamed("round(impossible_count, 0)","impossible_count_result")
impossible_df = impossible_df.select("context","question","is_impossible","answer_start","text","impossible_count_result")


impossible_rdd = impossible_df.rdd.map(lambda x:(x[0], x[1], x[2], x[3], x[4], x[5]))
impossible_rdd = impossible_rdd.flatMap(split_true_context)
impossible_result = spark.createDataFrame(impossible_rdd).cache()

result = positive_possible_result.union(impossible_result)
print(result.count())
result.show()
