# Databricks notebook source
# MAGIC %pip install --quiet --upgrade \
# MAGIC   databricks-sdk \
# MAGIC   databricks-vectorsearch \
# MAGIC   langchain \
# MAGIC   langchain-text-splitters \
# MAGIC   "anyio<4" \
# MAGIC   "protobuf<5"
# MAGIC
# MAGIC dbutils.library.restartPython()