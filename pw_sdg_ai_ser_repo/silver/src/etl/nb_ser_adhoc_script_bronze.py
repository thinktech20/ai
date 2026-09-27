# Databricks notebook source
# MAGIC %sql
# MAGIC DELETE FROM vaip.ai_std_con_field_service_report.er_failed_records WHERE last_error LIKE 'BACKFILL_AUDIT: source record had no chunks%'AND attempts = 0;
