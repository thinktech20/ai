# Databricks notebook source
# MAGIC %pip install --quiet --upgrade databricks-sdk databricks-vectorsearch langchain-text-splitters "anyio<4" "protobuf<5"
# MAGIC %pip uninstall -y databricks-connect
# MAGIC
# MAGIC dbutils.library.restartPython()