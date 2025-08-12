import streamlit as st
import json
from snowflake.core import Root # requires snowflake>=0.8.0
from snowflake.cortex import Complete
from snowflake.snowpark.context import get_active_session

# Enhanced RAG Demo with Intelligent Query Planning:
# 1. LLM Query Planner analyzes user intent (single doc, comparison, multi-doc)
# 2. For comparisons: Parallel document search + LLM synthesis
# 3. For single docs: Two-stage Cortex Search (metadata → chunks)
# 4. Fallback mechanisms ensure robust retrieval

MODELS = [
    "claude-4-sonnet"
]

def init_messages():
    """
    Initialize the session state for chat messages. If the session state indicates that the
    conversation should be cleared or if the "messages" key is not in the session state,
    initialize it as an empty list.
    """
    if st.session_state.clear_conversation or "messages" not in st.session_state:
        st.session_state.messages = []


def init_service_metadata():
    """
    Initialize the session state for cortex search service metadata. Query the available
    cortex search services from the Snowflake session and store their names and search
    columns in the session state.
    """
    if "service_metadata" not in st.session_state:
        services = session.sql("SHOW CORTEX SEARCH SERVICES;").collect()
        service_metadata = []
        if services:
            for s in services:
                svc_name = s["name"]
                svc_search_col = session.sql(
                    f"DESC CORTEX SEARCH SERVICE {svc_name};"
                ).collect()[0]["search_column"]
                service_metadata.append(
                    {"name": svc_name, "search_column": svc_search_col}
                )

        st.session_state.service_metadata = service_metadata


def init_config_options():
    """
    Initialize the configuration options in the Streamlit sidebar. Allow the user to
    clear the conversation, toggle debug mode, and toggle the use of chat history. 
    Also provide advanced options to select a model, the number of context chunks,
    and the number of chat messages to use in the chat history.
    """
    st.sidebar.button("Clear conversation", key="clear_conversation")
    st.sidebar.toggle("Debug", key="debug", value=False)
    st.sidebar.toggle("Use chat history", key="use_chat_history", value=True)

    with st.sidebar.expander("Advanced options"):
        st.selectbox("Select model:", MODELS, key="model_name")
        st.number_input(
            "Select number of context chunks",
            value=5,
            key="num_retrieved_chunks",
            min_value=1,
            max_value=20,
        )
        st.number_input(
            "Select number of messages to use in chat history",
            value=5,
            key="num_chat_messages",
            min_value=1,
            max_value=10,
        )

    st.sidebar.expander("Session State").write(st.session_state)


def query_cortex_search_service(query, columns = [], filter={}):
    """
    Query the selected cortex search service with the given query and retrieve context documents.
    Display the retrieved context documents in the sidebar if debug mode is enabled. Return the
    context documents as a string.

    Args:
        query (str): The query to search the cortex search service with.

    Returns:
        str: The concatenated string of context documents.
    """
    db, schema = session.get_current_database(), session.get_current_schema()

    cortex_search_service = (
        root.databases[db]
        .schemas[schema]
        .cortex_search_services[st.session_state.selected_cortex_search_service]
    )

    context_documents = cortex_search_service.search(
       #query, columns=columns, filter=filter, limit=st.session_state.num_retrieved_chunks
        query, columns=columns, limit=st.session_state.num_retrieved_chunks
    )
    results = context_documents.results

    service_metadata = st.session_state.service_metadata
    search_col = [s["search_column"] for s in service_metadata
                    if s["name"] == st.session_state.selected_cortex_search_service][0].lower()

    context_str = ""
    for i, r in enumerate(results):
        context_str += f"Context document {i+1}: {r[search_col]} \n" + "\n"

    if st.session_state.debug:
        st.sidebar.text_area("Context documents", context_str, height=500)

    return context_str, results


def query_metadata_search_service(query):
    """
    First stage: Query CS_DOCUMENTS_METADATA service to find relevant documents
    using the CONTENT_METADATA column.
    
    Args:
        query (str): The search query
        
    Returns:
        list: List of relevant filenames from metadata search
    """
    db, schema = session.get_current_database(), session.get_current_schema()
    
    # Query CS_DOCUMENTS_METADATA service
    metadata_service = (
        root.databases[db]
        .schemas[schema]
        .cortex_search_services["CS_DOCUMENTS_METADATA"]
    )
    
    # Search using CONTENT_METADATA column
    metadata_results = metadata_service.search(
        query=query,
        columns=["CONTENT_METADATA", "FILENAME"],  # Include filename to use as filter
        limit=50  # Increased limit for metadata results
    )
    
    # Extract filenames from metadata results
    relevant_filenames = []
    for result in metadata_results.results:
        # Handle both uppercase and lowercase filename keys
        filename = result.get("filename") or result.get("FILENAME")
        if filename:
            relevant_filenames.append(filename)
    
    if st.session_state.debug:
        debug_info = f"""
Metadata Search Query: {query}
Total metadata results: {len(metadata_results.results)}
Found {len(relevant_filenames)} relevant documents: {relevant_filenames}

Raw metadata results (first 3):
"""
        for i, result in enumerate(metadata_results.results[:3]):
            debug_info += f"\nResult {i+1}: {result}\n"
        
        st.sidebar.text_area("Metadata Search Debug", debug_info, height=200)
    
    return relevant_filenames


def query_chunks_search_service(query, relevant_filenames):
    """
    Second stage: Query CS_DOCUMENTS_CHUNKS service with filename filter
    to get the actual content chunks.
    
    Args:
        query (str): The search query
        relevant_filenames (list): List of filenames to filter by
        
    Returns:
        tuple: (context_str, results) - formatted context string and raw results
    """
    db, schema = session.get_current_database(), session.get_current_schema()
    
    # Query CS_DOCUMENTS_CHUNKS service
    chunks_service = (
        root.databases[db]
        .schemas[schema]
        .cortex_search_services["CS_DOCUMENTS_CHUNKS"]
    )
    
    # Create filter for filenames using @or with @eq conditions for multiple values
    # Note: @contains only works on ARRAY types, FILENAME is TEXT so we use @eq
    if relevant_filenames:
        if len(relevant_filenames) == 1:
            # Single filename - use simple @eq
            filename_filter = {"@eq": {"FILENAME": relevant_filenames[0]}}
        else:
            # Multiple filenames - use @or with multiple @eq conditions
            filename_filter = {
                "@or": [{"@eq": {"FILENAME": filename}} for filename in relevant_filenames]
            }
    else:
        filename_filter = {}
    
    # Search chunks with filename filter
    context_documents = chunks_service.search(
        query=query,
        columns=["contextualized_chunk", "filename", "file_url"],
        filter=filename_filter,
        limit=st.session_state.num_retrieved_chunks
    )
    
    results = context_documents.results
    
    # Build context string from chunk results
    context_str = ""
    for i, r in enumerate(results):
        context_str += f"Context document {i+1}: {r['contextualized_chunk']} \n" + "\n"
    
    if st.session_state.debug:
        st.sidebar.text_area("Chunks Search Results", 
                           f"Retrieved {len(results)} chunks from filtered documents", 
                           height=150)
        st.sidebar.text_area("Context documents", context_str, height=500)
    
    return context_str, results


def query_cortex_search_service_two_stage(query):
    """
    Two-stage search approach:
    1. Query CS_DOCUMENTS_METADATA to find relevant documents
    2. Query CS_DOCUMENTS_CHUNKS with filename filter to get actual content
    
    If the metadata search returns no results, fallback to searching all chunks.
    
    Args:
        query (str): The search query
        
    Returns:
        tuple: (context_str, results) - formatted context string and raw results
    """
    # Stage 1: Get relevant filenames from metadata search
    relevant_filenames = query_metadata_search_service(query)
    
    if not relevant_filenames:
        if st.session_state.debug:
            st.sidebar.warning("No relevant documents found in metadata search - falling back to search all chunks")
        # Fallback: Search all chunks without filename filter
        return query_chunks_search_service_fallback(query)
    
    # Stage 2: Get chunks from relevant documents only
    context_str, results = query_chunks_search_service(query, relevant_filenames)
    
    # If no chunks found even with filtered search, try fallback
    if not results:
        if st.session_state.debug:
            st.sidebar.warning("No chunks found in filtered search - falling back to search all chunks")
        return query_chunks_search_service_fallback(query)
    
    return context_str, results


def query_chunks_search_service_fallback(query):
    """
    Fallback function to search CS_DOCUMENTS_CHUNKS without any filename filter.
    
    Args:
        query (str): The search query
        
    Returns:
        tuple: (context_str, results) - formatted context string and raw results
    """
    db, schema = session.get_current_database(), session.get_current_schema()
    
    # Query CS_DOCUMENTS_CHUNKS service without filter
    chunks_service = (
        root.databases[db]
        .schemas[schema]
        .cortex_search_services["CS_DOCUMENTS_CHUNKS"]
    )
    
    # Search chunks without any filter
    context_documents = chunks_service.search(
        query=query,
        columns=["contextualized_chunk", "filename", "file_url"],
        limit=st.session_state.num_retrieved_chunks
    )
    
    results = context_documents.results
    
    # Build context string from chunk results
    context_str = ""
    for i, r in enumerate(results):
        context_str += f"Context document {i+1}: {r['contextualized_chunk']} \n" + "\n"
    
    if st.session_state.debug:
        st.sidebar.text_area("Fallback Search Results", 
                           f"Retrieved {len(results)} chunks from all documents", 
                           height=150)
        st.sidebar.text_area("Context documents", context_str, height=500)
    
    return context_str, results


def analyze_query_intent(user_question):
    """
    Use LLM to analyze the user's question and determine the optimal search strategy.
    
    Args:
        user_question (str): The user's question
        
    Returns:
        dict: Analysis result with query type, documents, and search strategy
    """
    prompt = f"""
    Analyze this user question and determine the search strategy needed:
    
    Question: "{user_question}"
    
    Determine:
    1. Query type: 
       - "single_document": Looking for info from one document or general topic
       - "comparison": Comparing 2+ specific documents or entities  
       - "multi_document": Asking about multiple separate topics/documents
       - "general": General question not tied to specific documents
    
    2. If comparison or multi_document, extract the specific document names or key topics
    
    3. Create search queries - for comparisons, create separate queries for each document
    
    4. Analysis type needed for final response
    
    Respond in valid JSON format only:
    {{
        "query_type": "comparison|single_document|multi_document|general",
        "documents": ["document name 1", "document name 2"],
        "search_queries": ["search query 1", "search query 2"],
        "analysis_type": "comparison|synthesis|standard",
        "reasoning": "brief explanation of the analysis"
    }}
    
    Examples:
    - "Compare X and Y agreements" → comparison type, separate searches for X and Y
    - "What are the terms in the X contract?" → single_document type  
    - "Tell me about privacy policies" → general type
    """
    
    try:
        response = Complete(st.session_state.model_name, prompt)
        # Clean the response to extract JSON
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:-3]
        elif response.startswith('```'):
            response = response[3:-3]
        
        analysis = json.loads(response)
        
        if st.session_state.debug:
            st.sidebar.text_area("Query Analysis", 
                               f"Type: {analysis.get('query_type')}\nDocuments: {analysis.get('documents')}\nReasoning: {analysis.get('reasoning')}", 
                               height=150)
        
        return analysis
    except (json.JSONDecodeError, Exception) as e:
        if st.session_state.debug:
            st.sidebar.error(f"Query analysis failed: {str(e)}")
        # Fallback to single document search
        return {
            "query_type": "single_document",
            "documents": [],
            "search_queries": [user_question],
            "analysis_type": "standard",
            "reasoning": "Fallback due to analysis error"
        }


def search_specific_document(document_name, search_query):
    """
    Search for a specific document using two-stage approach with document name focus.
    
    Args:
        document_name (str): Name of the document to search for
        search_query (str): The search query
        
    Returns:
        tuple: (context_str, results) - formatted context and raw results
    """
    # Stage 1: Search metadata with document name emphasis
    metadata_query = f"{document_name} {search_query}"
    relevant_filenames = query_metadata_search_service(metadata_query)
    
    # Filter filenames to prioritize those containing the document name
    prioritized_filenames = []
    other_filenames = []
    
    for filename in relevant_filenames:
        # Check if filename contains key words from document name
        doc_words = document_name.lower().split()
        filename_lower = filename.lower()
        if any(word in filename_lower for word in doc_words if len(word) > 3):
            prioritized_filenames.append(filename)
        else:
            other_filenames.append(filename)
    
    # Use prioritized filenames first, then others
    final_filenames = prioritized_filenames + other_filenames
    
    if not final_filenames:
        if st.session_state.debug:
            st.sidebar.warning(f"No files found for document: {document_name}")
        return "", []
    
    # Stage 2: Get chunks from relevant documents
    context_str, results = query_chunks_search_service(search_query, final_filenames[:10])  # Limit to top 10
    
    if st.session_state.debug:
        st.sidebar.text_area(f"Document Search: {document_name}", 
                           f"Query: {search_query}\nPrioritized files: {prioritized_filenames}\nChunks found: {len(results)}", 
                           height=100)
    
    return context_str, results


def synthesize_comparison_results(comparison_results, original_question):
    """
    Use LLM to synthesize and compare results from multiple document searches.
    
    Args:
        comparison_results (list): List of (document_name, context_str, results) tuples
        original_question (str): The original user question
        
    Returns:
        tuple: (synthesized_response, combined_results)
    """
    # Build comprehensive context from all documents
    synthesis_context = ""
    combined_results = []
    
    for i, (doc_name, context_str, results) in enumerate(comparison_results):
        synthesis_context += f"\n=== {doc_name} ===\n{context_str}\n"
        combined_results.extend(results)
    
    synthesis_prompt = f"""
    You are analyzing multiple documents to answer a comparison or multi-document question.
    
    Original Question: {original_question}
    
    Document Information:
    {synthesis_context}
    
    Instructions:
    1. If this is a comparison question, provide a structured comparison highlighting:
       - Key similarities between the documents
       - Important differences 
       - Specific terms, conditions, or clauses that differ
       - Business or practical implications
    
    2. If this is a multi-document question, synthesize information from all sources:
       - Combine relevant information from all documents
       - Note where information comes from which document
       - Provide a comprehensive answer
    
    3. Be specific and cite which document contains which information
    4. If documents are missing or information is incomplete, note this clearly
    5. Focus on directly answering the user's question
    
    Provide a clear, well-structured response that directly addresses the user's question.
    """
    
    synthesized_response = Complete(st.session_state.model_name, synthesis_prompt)
    
    if st.session_state.debug:
        st.sidebar.text_area("Synthesis Context", synthesis_context[:1000] + "..." if len(synthesis_context) > 1000 else synthesis_context, height=200)
    
    return synthesized_response, combined_results


def intelligent_search_orchestrator(user_question):
    """
    Orchestrates the intelligent search workflow based on query analysis.
    
    Args:
        user_question (str): The user's question
        
    Returns:
        tuple: (response_text, results, is_synthesized)
    """
    # Step 1: Analyze the query intent
    analysis = analyze_query_intent(user_question)
    query_type = analysis.get("query_type", "single_document")
    documents = analysis.get("documents", [])
    search_queries = analysis.get("search_queries", [user_question])
    analysis_type = analysis.get("analysis_type", "standard")
    
    if st.session_state.debug:
        st.sidebar.markdown(f"**Workflow:** {query_type.replace('_', ' ').title()}")
    
    # Step 2: Route to appropriate workflow
    if query_type == "comparison" and len(documents) >= 2:
        # Comparison workflow: Search each document separately
        comparison_results = []
        
        for i, (doc_name, search_query) in enumerate(zip(documents, search_queries)):
            context_str, results = search_specific_document(doc_name, search_query)
            comparison_results.append((doc_name, context_str, results))
            
            if st.session_state.debug:
                st.sidebar.text_area(f"Search {i+1}: {doc_name}", 
                                   f"Found {len(results)} chunks", height=50)
        
        # Synthesize comparison
        if any(results for _, _, results in comparison_results):
            response_text, combined_results = synthesize_comparison_results(comparison_results, user_question)
            return response_text, combined_results, True
        else:
            # Fallback to standard search if no results
            if st.session_state.debug:
                st.sidebar.warning("No comparison results found, falling back to standard search")
            return query_cortex_search_service_two_stage(user_question) + (False,)
    
    elif query_type == "multi_document" and len(documents) > 1:
        # Multi-document workflow: Search each document/topic separately
        multi_results = []
        
        for i, (doc_name, search_query) in enumerate(zip(documents, search_queries)):
            if doc_name:  # If specific document name provided
                context_str, results = search_specific_document(doc_name, search_query)
            else:  # If general topic
                context_str, results = query_cortex_search_service_two_stage(search_query)
            multi_results.append((doc_name or f"Topic {i+1}", context_str, results))
        
        # Synthesize multi-document results
        if any(results for _, _, results in multi_results):
            response_text, combined_results = synthesize_comparison_results(multi_results, user_question)
            return response_text, combined_results, True
        else:
            # Fallback to standard search
            return query_cortex_search_service_two_stage(user_question) + (False,)
    
    else:
        # Single document or general workflow: Use standard two-stage search
        context_str, results = query_cortex_search_service_two_stage(user_question)
        return context_str, results, False


def get_chat_history():
    """
    Retrieve the chat history from the session state limited to the number of messages specified
    by the user in the sidebar options.

    Returns:
        list: The list of chat messages from the session state.
    """
    start_index = max(
        0, len(st.session_state.messages) - st.session_state.num_chat_messages
    )
    return st.session_state.messages[start_index : len(st.session_state.messages) - 1]


def complete(model, prompt):
    """
    Generate a completion for the given prompt using the specified model.

    Args:
        model (str): The name of the model to use for completion.
        prompt (str): The prompt to generate a completion for.

    Returns:
        str: The generated completion.
    """
    return Complete(model, prompt).replace("$", "\$")


def make_chat_history_summary(chat_history, question):
    """
    Generate a summary of the chat history combined with the current question to extend the query
    context. Use the language model to generate this summary.

    Args:
        chat_history (str): The chat history to include in the summary.
        question (str): The current user question to extend with the chat history.

    Returns:
        str: The generated summary of the chat history and question.
    """
    prompt = f"""
        [INST]
        Based on the chat history below and the question, generate a query that extend the question
        with the chat history provided. The query should be in natural language.
        Answer with only the query. Do not add any explanation.

        <chat_history>
        {chat_history}
        </chat_history>
        <question>
        {question}
        </question>
        [/INST]
    """

    summary = complete(st.session_state.model_name, prompt)

    if st.session_state.debug:
        st.sidebar.text_area(
            "Chat history summary", summary.replace("$", "\$"), height=150
        )

    return summary


def create_prompt(user_question):
    """
    Create a response using the intelligent search orchestrator that handles single documents,
    comparisons, and multi-document queries. Uses chat history when enabled.

    Args:
        user_question (str): The user's question to generate a response for.

    Returns:
        tuple: The generated response and the search results.
    """
    # Handle chat history if enabled
    final_question = user_question
    chat_history = ""
    
    if st.session_state.use_chat_history:
        chat_history = get_chat_history()
        if chat_history != []:
            final_question = make_chat_history_summary(chat_history, user_question)
    
    # Use intelligent orchestrator to get response
    response_text, results, is_synthesized = intelligent_search_orchestrator(final_question)
    
    # If we got a synthesized response (comparison/multi-doc), return it directly
    if is_synthesized:
        return response_text, results
    
    # For standard single-document responses, format with chat history context
    prompt_context = response_text  # response_text is actually context_str for non-synthesized
    
    prompt = f"""
            [INST]
            You are a helpful AI chat assistant with RAG capabilities. When a user asks you a question,
            you will also be given context provided between <context> and </context> tags. Use that context
            with the user's chat history provided in the between <chat_history> and </chat_history> tags
            to provide a summary that addresses the user's question. Ensure the answer is coherent, concise,
            and directly relevant to the user's question.

            If the user asks a generic question which cannot be answered with the given context or chat_history,
            just say "I don't know the answer to that question.

            Don't saying things like "according to the provided context".

            <chat_history>
            {chat_history}
            </chat_history>
            <context>
            {prompt_context}
            </context>
            <question>
            {user_question}
            </question>
            [/INST]
            Answer:
            """
    
    # Generate final response using LLM
    final_response = Complete(st.session_state.model_name, prompt)
    return final_response, results


def build_enhanced_references(results):
    """
    Build an enhanced references section with chunk previews and deduplication.
    
    Args:
        results (list): List of search results with filename, file_url, and chunk content
        
    Returns:
        str: Formatted markdown references section
    """
    if not results:
        return ""
    
    # Deduplicate by filename and collect chunks per document
    document_chunks = {}
    seen_filenames = set()
    
    for i, result in enumerate(results):
        if not isinstance(result, dict):
            continue
            
        # Handle different possible key formats (case-insensitive)
        filename = result.get('filename') or result.get('FILENAME')
        file_url = result.get('file_url') or result.get('FILE_URL')
        chunk_content = (result.get('contextualized_chunk') or 
                        result.get('CONTEXTUALIZED_CHUNK') or 
                        result.get('chunk') or 
                        result.get('CHUNK'))
        
        if not filename:
            continue
            
        # Create a clean document name for display
        display_name = filename.replace('.pdf', '').replace('.docx', '').replace('.txt', '')
        if len(display_name) > 50:
            display_name = display_name[:47] + "..."
        
        if filename not in document_chunks:
            document_chunks[filename] = {
                'display_name': display_name,
                'file_url': file_url,
                'chunks': [],
                'first_seen_index': i
            }
        
        # Add chunk preview (first 150 chars)
        if chunk_content:
            # Clean chunk content and create preview
            clean_chunk = chunk_content.replace('\n', ' ').strip()
            if len(clean_chunk) > 150:
                chunk_preview = clean_chunk[:147] + "..."
            else:
                chunk_preview = clean_chunk
            
            # Only add unique chunk previews
            if chunk_preview not in [chunk['preview'] for chunk in document_chunks[filename]['chunks']]:
                document_chunks[filename]['chunks'].append({
                    'preview': chunk_preview,
                    'index': i + 1
                })
    
    if not document_chunks:
        return ""
    
    # Sort documents by first appearance in results
    sorted_docs = sorted(document_chunks.items(), 
                        key=lambda x: x[1]['first_seen_index'])
    
    # Build enhanced references section
    references_md = "###### 📚 Sources & References\n\n"
    
    for filename, doc_info in sorted_docs:
        display_name = doc_info['display_name']
        file_url = doc_info['file_url']
        chunks = doc_info['chunks']
        
        # Document header with link
        if file_url:
            references_md += f"**📄 [{display_name}]({file_url})**\n"
        else:
            references_md += f"**📄 {display_name}**\n"
        
        # Add chunk previews
        if chunks:
            for chunk in chunks[:3]:  # Limit to top 3 chunks per document
                references_md += f"- *Excerpt {chunk['index']}:* \"{chunk['preview']}\"\n"
        
        references_md += "\n"
    
    # Add summary if many documents
    if len(sorted_docs) > 1:
        total_chunks = sum(len(doc_info['chunks']) for _, doc_info in sorted_docs)
        references_md += f"*📊 Total: {len(sorted_docs)} documents, {total_chunks} relevant excerpts*\n"
    
    return references_md


def main():
    st.title(f":speech_balloon: Chatbot with Snowflake Cortex")

    init_service_metadata()
    init_config_options()
    init_messages()

    icons = {"assistant": "❄️", "user": "👤"}

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar=icons[message["role"]]):
            st.markdown(message["content"])

    if question := st.chat_input("Ask a question..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": question})
        # Display user message in chat message container
        with st.chat_message("user", avatar=icons["user"]):
            st.markdown(question.replace("$", "\$"))

        # Display assistant response in chat message container
        with st.chat_message("assistant", avatar=icons["assistant"]):
            message_placeholder = st.empty()
            question = question.replace("'", "")
            with st.spinner("Analyzing question and searching documents..."):
                generated_response, results = create_prompt(question)
                
                # Build enhanced references with chunk previews and deduplication
                references_section = build_enhanced_references(results)
                
                if references_section:
                    message_placeholder.markdown(generated_response + "\n\n" + references_section)
                else:
                    message_placeholder.markdown(generated_response)

        st.session_state.messages.append(
            {"role": "assistant", "content": generated_response}
        )


if __name__ == "__main__":
    session = get_active_session()
    root = Root(session)
    main()