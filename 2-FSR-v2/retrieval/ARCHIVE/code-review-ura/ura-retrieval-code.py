=======================


equipment_service.py:

        async def _retrieve_multi_esn_document(
    esn: str | None,
) -> tuple[bool, list[str]]:
    """Fetch eligible FSR document IDs from the multi-ESN table for the given ESN.
    Queries the multi-ESN document table (joined with the v2 metadata table) for
    active, fully-chunked documents matching the given ESN, optionally restricted
    to the configured lookback window.
    Args:
        esn: Equipment Serial Number to filter documents for.
    Returns:
        A tuple of (success, document_ids):
            - (True, list[str]): Non-empty list of eligible document_id strings.
            - (False, []): If the query failed or returned no rows.
    """
    sanitized_esn = esn
    db_client = DatabricksClient()

    # Filters: is_active=true, chunk_status='completed', recency.
    # Date filter applied here in SQL — no need to repeat in VS filtering_json.
    recency_clause = (
        f"AND m.outage_start_date >= DATE_FORMAT(ADD_MONTHS(CURRENT_DATE(), -{_FSR_LOOKBACK_MONTHS}), 'yyyy-MM-dd')"
        if _FSR_LOOKBACK_SET else ""
    )
    try:
        multi_esn_rows = await db_client.query_async(
            f"SELECT DISTINCT d.document_id "
            f"FROM {_FSR_MULTI_ESN_TABLE} d "
            f"INNER JOIN {_FSR_METADATA_V2_TABLE} m ON d.document_id = m.document_id "
            f"WHERE UPPER(d.esn) = UPPER(:sanitized_esn) "
            f"  AND d.is_active = true "
            f"  AND m.chunk_status = 'completed' "
            f"  {recency_clause}",
            {"sanitized_esn": sanitized_esn},
        )
    except Exception as e:
        logger.error("Multi-ESN document lookup failed for esn=%s: %s", sanitized_esn, e, exc_info=True)
        return False, []

    multi_esn_doc_ids = [
        str(r["document_id"]).strip() for r in multi_esn_rows if r.get("document_id")
    ]

    if not multi_esn_doc_ids:
        logger.info("No documents found in multi-ESN table for esn=%s.", sanitized_esn)
        return False, []

    logger.info("Multi-ESN table returned %d document_ids for esn=%s", len(multi_esn_doc_ids), sanitized_esn)
    return True, multi_esn_doc_ids
===
retriever_service.py:

#Retrieve the recent Document IDs
    pdf_search_list = []
    use_multi_esn_index = False
    if _FSR_LOOKBACK_SET:
        # Check the multi-ESN table first; fall back to the timeboxed primary index only if
        # no documents are found there.
        success, multi_esn_doc_ids = await _retrieve_multi_esn_document(sanitized_esn)

        if success:
            use_multi_esn_index = True
            # Date already filtered in SQL gate — VS filter uses document_id only
            filtering_json = json.dumps({
                "region_primary_esn": sanitized_esn,
                "document_id": multi_esn_doc_ids,
            })
        else:
            logger.info("No FSR documents in multi-ESN table for esn=%s. Falling back to timeboxed index.", sanitized_esn)
            success, pdf_search_list = await _retrieve_timeboxed_document(sanitized_esn)

            if not success:
                logger.info("No documents found in timeboxed index for esn=%s. Skipping vector search.", sanitized_esn)
                for item in issue_prompts:
                    result_data[item.get("issue_id", "")] = []
                return json.dumps({"data": result_data})

            filtering_json = json.dumps({
                        "esn": sanitized_esn,
                        "document_id": pdf_search_list
                    })
    else:
        filtering_json = json.dumps({
                        "esn": sanitized_esn,
                    })
        logger.info(f"No lookback implemented. Sending a document list with {len(pdf_search_list)} rows")

================================================


 # ========== STEP 2: Retrieve chunks through Hybrid Search ==========
        try:
            search_index = _FSR_MULTI_ESN_INDEX if use_multi_esn_index else cfg['index']
            logger.info("Using FSR search index: %s", search_index)
            search_columns = ["chunk_id", "pdf_name", "page_number", "chunk_text", "region_primary_esn"] if use_multi_esn_index else ["chunk_id", "pdf_name", "page_number", "chunk_text", "esn"]
            #logger.info(f"Vector Index: {cfg['workspace_url']}/api/2.0/vector-search/indexes/{search_index}/query")
            #logger.info(f"Bearer {cfg['token']}")
            query_json={
                    "query_text": sanitized_query,
                    "query_vector": issue_prompt_embedding,
                    "filters_json": filtering_json,
                    "num_results": top_k,
                    "query_type": "HYBRID",
                    "columns": search_columns,
                }
            #logger.info(f"Json input: {query_json}")
            response = requests.post(
                f"{cfg['workspace_url']}/api/2.0/vector-search/indexes/{search_index}/query",
                headers={
                    "Authorization": f"Bearer {cfg['token']}",
                    "Content-Type": "application/json",
                },
                json=query_json,
                timeout=300,
                verify=False,
            )
            response.raise_for_status()
            search_results = response.json()
        except requests.exceptions.Timeout:
            logger.error("Vector search timed out for issue_id='%s'", issue_id)
            result_data[issue_id] = []
            continue
        except requests.exceptions.HTTPError as e:
            logger.error(
                "Vector search HTTP error for issue_id='%s': %d: %s",
                issue_id, e.response.status_code, e.response.text[:200], exc_info=True,
            )
            result_data[issue_id] = []
            continue
        except (requests.exceptions.RequestException, Exception) as e:
            logger.error(
                "Vector search request failed for issue_id='%s': %s: %s",
                issue_id, type(e).__name__, e, exc_info=True,
            )
            result_data[issue_id] = []
            continue

        data = search_results.get("result", {}).get("data_array", [])
        logger.info("Vector search returned %d results for issue_id='%s'", len(data), issue_id)

        if not data:
            result_data[issue_id] = []
            continue

    ===============

