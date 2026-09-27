# Databricks notebook source
import pandas as pd
from pyspark.sql.functions import col
import pyspark.sql.functions as F

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create required widget parameters

# COMMAND ----------

# Define the widgets for catalog and file path
dbutils.widgets.text("catalog", "hive_metastore", "Catalog")
dbutils.widgets.text("file_path", "/Workspace/Shared/GasPower/FDC_Custom_EDL/metadata.csv", "File Path")
dbutils.widgets.text("sub_domain_code", "", "3 character Sub domain code")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Get the parameters needed for this run

# COMMAND ----------

# Load the file into a dataframe
file_path = dbutils.widgets.get("file_path")
catalog = dbutils.widgets.get("catalog")
sub_domain_code = dbutils.widgets.get("sub_domain_code")
print(file_path)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Map the input file schema

# COMMAND ----------

#Input file schema
ip_file_schema = {"Catalog":"catalog","Schema":"schema","Table":"table","Table Description":"table_comment","Column Name":"column_name","Column Description":"column_comment","Domain":"domain","Sub-Domain-Code":"sub_domain_code","Naksha Tag":"naksha_tag"}

# COMMAND ----------

# MAGIC %md
# MAGIC ## Metadata Update

# COMMAND ----------

# MAGIC %md
# MAGIC ### Create the input dataframe for the metadata update

# COMMAND ----------

#Prepare the input data
pd_ip_file_comments = pd.read_csv(file_path,usecols=ip_file_schema.keys())
pd_ip_file_comments = pd_ip_file_comments.rename(columns=ip_file_schema)
ip_file_comments = spark.createDataFrame(pd_ip_file_comments)
ip_file_comments=ip_file_comments.na.replace(float('nan'), None)
ip_file_comments.createOrReplaceTempView("ip_file_comments")

#Filter for sub domain and naksha eligible
#ip_file_comments_sb = ip_file_comments.filter(ip_file_comments.sub_domain_code == sub_domain_code).select(['schema','table','naksha_tag']).distinct()
#ip_file_comments_sb.createOrReplaceTempView('ip_file_comments_sb')

ip_file_comments = spark.sql(f"""                            
                            WITH ip_file_comments_naksha as (
                                SELECT distinct schema,table,naksha_tag 
                                FROM 
                                ip_file_comments 
                                WHERE 
                                naksha_tag is not null 
                                and sub_domain_code = '{sub_domain_code}')                            
                            SELECT ip_file_comments.* 
                            FROM ip_file_comments join ip_file_comments_naksha on ip_file_comments.schema = ip_file_comments_naksha.schema and ip_file_comments.table = ip_file_comments_naksha.table where ip_file_comments.catalog = '{catalog}'
                            """)

#ip_file_comments.display()
#spark.catalog.dropTempView("ip_file_comments_sb")


# COMMAND ----------

# MAGIC %md
# MAGIC ### Get the distinct tables from the list

# COMMAND ----------

# Get distinct schema and table from file dataframe
distinct_schemas_tables = ip_file_comments.select("schema", "table").distinct()
distinct_schemas_tables.createOrReplaceTempView("distinct_schemas_tables")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Table Metadata update

# COMMAND ----------

# MAGIC %md
# MAGIC #### Get existing metadata

# COMMAND ----------

# Query the information schema only for those schema and tables
information_schema_tables = spark.sql(f"""
    SELECT 
        c.TABLE_SCHEMA AS table_schema,
        c.TABLE_NAME AS table_name,
        c.comment as table_comment,
        c.table_type as table_type
    FROM 
        {catalog}.information_schema.tables c
    INNER JOIN 
        distinct_schemas_tables d
    ON c.TABLE_SCHEMA = d.schema AND c.TABLE_NAME = d.table
""")
#information_schema_tables.display()
information_schema_tables.createOrReplaceTempView('information_schema_tables')

# COMMAND ----------

# MAGIC %md
# MAGIC #### Compare and update comments based on change

# COMMAND ----------

# Check if the comments match between information schema and file dataframe and perform comment on operation if it is not matching
df_table_comments = ip_file_comments.filter(ip_file_comments.table_comment.isNotNull())
df_table_comments.createOrReplaceTempView('table_comments')

# Merge the two dataframes
merged_tables_df = spark.sql(f"""
                             select ip.schema as schema,ip.table as table,ist.table_type as table_type,replace(ip.table_comment,"'","") as ip_table_comment,ist.table_comment as ist_table_comment from table_comments ip left join information_schema_tables ist on ip.schema = ist.table_schema and ip.table = ist.table_name
                             """)
merged_tables_df.createOrReplaceTempView("merged_tables_comment")

# Filter the columns that need to be updated
update_comments = spark.sql(f"""
                             select schema,table,table_type,ip_table_comment,ist_table_comment from merged_tables_comment where ip_table_comment IS DISTINCT FROM ist_table_comment and ip_table_comment is not null
                             """)
#merged_tables_df.filter((merged_tables_df.ip_table_comment != merged_tables_df.ist_table_comment) & (merged_tables_df.ip_table_comment.isNotNull()))
# Update the comments
update_count = 0
#update_comments.display()

for row in update_comments.collect():
    table_name = row.table
    new_comment = row.ip_table_comment
    table_type = row.table_type
    # Update the comment
    #sql=f"""COMMENT ON TABLE `{catalog}`.`{row.schema}`.`{table_name}` IS '{new_comment.replace("'","")}'"""
    sql=f"""ALTER {table_type} `{catalog}`.`{row.schema}`.`{table_name}` SET TBLPROPERTIES ('comment' = '{new_comment.replace("'","")}')"""
    #print(sql)
    spark.sql(sql)
    update_count += 1

# Display the number of column comments updated or added
display(update_count)



# COMMAND ----------

# MAGIC %md
# MAGIC #### Get Existing Naksha tags

# COMMAND ----------

# Query the information schema only for those schema and tables
information_schema_tags = spark.sql(f"""
    SELECT 
        c.schema_name AS table_schema,
        c.table_name AS table_name,
        c.tag_name as tag_name,
        c.tag_value as tag_value
    FROM 
        {catalog}.information_schema.table_tags c
    LEFT JOIN 
        distinct_schemas_tables d
    ON c.schema_name = d.schema AND c.table_name = d.table WHERE c.tag_name = 'naksha'
""")
#information_schema_tags.display()
information_schema_tags.createOrReplaceTempView('information_schema_tags')

# COMMAND ----------

# MAGIC %md
# MAGIC #### Compare and update tags based on change

# COMMAND ----------

# Check if the comments match between information schema and file dataframe and perform comment on operation if it is not matching
df_table_comments = ip_file_comments.filter(ip_file_comments.table_comment.isNotNull())
df_table_comments.createOrReplaceTempView('table_comments')
# Merge the two dataframes
merged_tags_df = spark.sql(f"""
                             select ip.schema as schema,ip.table as table,ip.naksha_tag as ip_naksha_tag,ist.tag_value as ist_naksha_tag from table_comments ip left join information_schema_tags ist on ip.schema = ist.table_schema and ip.table = ist.table_name
                             """)
#merged_tags_df.display()
merged_tags_df.createOrReplaceTempView("merged_tables_tags")

# Filter the columns that need to be updated
update_tags = spark.sql(f"""
                             select schema,table,ip_naksha_tag,ist_naksha_tag from merged_tables_tags where ip_naksha_tag is not null and ip_naksha_tag IS DISTINCT FROM ist_naksha_tag 
                             """)
#update_tags.display()
#merged_tables_df.filter((merged_tables_df.ip_table_comment != merged_tables_df.ist_table_comment) & (merged_tables_df.ip_table_comment.isNotNull()))

# Update the comments
update_count = 0
for row in update_tags.collect():
    
    # Update the comment
    sql=f"""ALTER TABLE `{catalog}`.`{row.schema}`.`{row.table}` SET TAGS ('naksha' = '{row.ip_naksha_tag}')"""
    #print(sql)
    spark.sql(sql)
    update_count += 1

# Display the number of column comments updated or added
display(update_count)

#update_tags.display()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Column metadata update

# COMMAND ----------

# MAGIC %md
# MAGIC #### Get existing metadata

# COMMAND ----------

# Query the information schema only for those schema and tables
information_schema_columns = spark.sql(f"""
    SELECT 
        c.TABLE_SCHEMA AS schema,
        c.TABLE_NAME AS table,
        d.TABLE_TYPE as table_type,
        c.COLUMN_NAME AS column,
        c.COMMENT AS comment
    FROM 
        information_schema_tables d
    LEFT JOIN 
        {catalog}.information_schema.columns c
    ON c.TABLE_SCHEMA = d.table_schema AND c.TABLE_NAME = d.table_name
""")
information_schema_columns.display()
information_schema_columns.createOrReplaceTempView('information_schema_columns')

# COMMAND ----------

# MAGIC %md
# MAGIC #### Compare and update comments based on change

# COMMAND ----------

# Check if the comments match between information schema and file dataframe and perform comment on operation if it is not matching

df_column_comments = ip_file_comments.filter(ip_file_comments.column_comment.isNotNull())
df_column_comments.createOrReplaceTempView('column_comments')
#df_column_comments.display()

# Merge the two dataframes
merged_column_comment = spark.sql(f"""
                             select ip.schema as schema,ip.table as table,isc.table_type as table_type,ip.column_name as column,replace(ip.column_comment,"'","") as ip_column_comment,isc.comment as isc_column_comment from column_comments ip left join information_schema_columns isc on ip.schema = isc.schema and ip.table = isc.table and ip.column_name = isc.column
                             """)
merged_column_comment.createOrReplaceTempView("merged_column_comment")
#merged_column_comment.display()

# Filter the columns that need to be updated
update_comments = spark.sql(f"""
                             select schema,table,table_type,column,ip_column_comment,isc_column_comment from merged_column_comment where ip_column_comment IS DISTINCT FROM isc_column_comment and ip_column_comment is not null
                             """)
#update_comments = merged_tables_df.filter((merged_tables_df.ip_column_comment != merged_tables_df.isc_column_comment) & (merged_tables_df.ip_column_comment.isNotNull()))
#update_comments.display()

# Update the comments
update_count = 0
for row in update_comments.collect():
    table_name = row.table
    new_comment = row.ip_column_comment
    table_type = row.table_type
    
    sql = ""
    # Update the comment
    if table_type == 'VIEW':

        sql=f"""COMMENT ON COLUMN `{catalog}`.`{row.schema}`.`{table_name}`.`{row.column}` IS '{new_comment}'"""
    else:
        sql=f"""ALTER TABLE `{catalog}`.`{row.schema}`.`{table_name}` ALTER COLUMN `{row.column}` COMMENT '{new_comment}'"""
    #print(sql)
    spark.sql(sql)
    update_count += 1

# Display the number of column comments updated or added
display(update_count)