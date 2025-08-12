import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime
from snowflake.core import Root
from snowflake.cortex import Complete
from snowflake.snowpark.context import get_active_session
from typing import Dict, List, Any, Optional

# TruLens imports for evaluation and observability
try:
    from trulens.core.otel.instrument import instrument
    from trulens.otel.semconv.trace import SpanAttributes
    from trulens.apps.app import TruApp
    from trulens.connectors.snowflake import SnowflakeConnector
    TRULENS_AVAILABLE = True
    # Enable TruLens OpenTelemetry tracing
    os.environ["TRULENS_OTEL_TRACING"] = "1"
except ImportError:
    TRULENS_AVAILABLE = False
    st.warning("⚠️ TruLens not available. Install trulens packages for full evaluation capabilities.")

# Enhanced RAG Demo with AI Observability & User Feedback:
# 1. TruLens instrumentation for comprehensive tracing
# 2. User feedback collection and analysis
# 3. Evaluation metrics and performance monitoring
# 4. LLM Query Planner with intelligent orchestration
# 5. Multi-stage retrieval with fallback mechanisms

MODELS = ["claude-4-sonnet"]

def conditional_instrument():
    """Conditional decorator that only applies instrumentation if TruLens is available."""
    def decorator(func):
        if TRULENS_AVAILABLE:
            try:
                return instrument()(func)  # Basic instrumentation
            except (AttributeError, ImportError):
                return func  # Fallback if instrumentation fails
        return func
    return decorator

class InstrumentedRAGChatbot:
    """
    Enhanced RAG chatbot with TruLens instrumentation and user feedback collection.
    """
    
    def __init__(self, session):
        self.session = session
        self.root = Root(session)
    
    @conditional_instrument()
    def analyze_query_intent(self, user_question: str) -> Dict[str, Any]:
        """Analyze user query intent with optional instrumentation."""
        prompt = f"""
        Analyze the following user question and determine:
        1. Query type: single_document, comparison, multi_document, or general
        2. Specific document names or topics mentioned
        3. Suggested search queries for retrieval
        
        User question: {user_question}
        
        Respond in JSON format:
        {{
            "query_type": "...",
            "documents": [...],
            "search_queries": [...]
        }}
        """
        
        try:
            response = Complete("claude-4-sonnet", prompt)
            return json.loads(response)
        except (json.JSONDecodeError, Exception) as e:
            return {
                "query_type": "single_document",
                "documents": [],
                "search_queries": [user_question]
            }
    
    @conditional_instrument()
    def query_metadata_search_service(self, query: str, limit: int = 50) -> List[Dict]:
        """Query metadata search service with optional instrumentation."""
        try:
            # Get current database and schema dynamically
            db, schema = self.session.get_current_database(), self.session.get_current_schema()
            
            # Debug information
            st.sidebar.write(f"🔍 Using database: {db}, schema: {schema}")
            
            search_service = (
                self.root.databases[db]
                .schemas[schema]
                .cortex_search_services["CS_DOCUMENTS_METADATA"]
            )
            
            response = search_service.search(
                query=query,
                columns=["FILENAME"],
                limit=limit
            )
            
            return response.results if response.results else []
        except Exception as e:
            st.error(f"Error in metadata search: {e}")
            return []
    
    @conditional_instrument()
    def query_chunks_search_service(self, query: str, relevant_filenames: List[str], limit: int = 10) -> List[Dict]:
        """Query chunks search service with filtering and optional instrumentation."""
        try:
            # Get current database and schema dynamically
            db, schema = self.session.get_current_database(), self.session.get_current_schema()
            
            search_service = (
                self.root.databases[db]
                .schemas[schema]
                .cortex_search_services["CS_DOCUMENTS_CHUNKS"]
            )
            
            if len(relevant_filenames) == 1:
                filter_dict = {"@eq": {"FILENAME": relevant_filenames[0]}}
            else:
                filter_dict = {"@or": [{"@eq": {"FILENAME": filename}} for filename in relevant_filenames]}
            
            response = search_service.search(
                query=query,
                columns=["contextualized_chunk", "filename", "file_url"],
                limit=limit,
                filter=filter_dict
            )
            
            return response.results if response.results else []
        except Exception as e:
            st.error(f"Error in chunks search: {e}")
            return []
    
    @conditional_instrument()
    def generate_completion(self, user_question: str, context_str: str) -> str:
        """Generate completion with optional instrumentation."""
        prompt = f"""
        You are an expert legal document analysis assistant. Based on the provided context from legal contracts,
        provide a comprehensive and accurate answer to the user's question.
        
        Context: {context_str}
        
        Question: {user_question}
        
        Answer:
        """
        
        return Complete("claude-4-sonnet", prompt)
    
    @conditional_instrument()
    def intelligent_search_orchestrator(self, user_question: str) -> Dict[str, Any]:
        """
        Main orchestrator with full optional instrumentation.
        """
        # Analyze query intent
        intent_analysis = self.analyze_query_intent(user_question)
        
        # Get relevant documents from metadata search
        metadata_results = self.query_metadata_search_service(user_question)
        
        if not metadata_results:
            return {
                "response": "I couldn't find relevant documents for your query. Please try rephrasing your question.",
                "results": [],
                "intent_analysis": intent_analysis,
                "search_strategy": "no_results"
            }
        
        # Extract filenames and search chunks
        relevant_filenames = [result.get('FILENAME') for result in metadata_results if result.get('FILENAME')]
        chunk_results = self.query_chunks_search_service(user_question, relevant_filenames)
        
        if not chunk_results:
            return {
                "response": "I found relevant documents but couldn't extract specific information. Please provide more specific details.",
                "results": [],
                "intent_analysis": intent_analysis,
                "search_strategy": "metadata_only"
            }
        
        # Generate response
        context_str = "\n\n".join([result.get('contextualized_chunk', '') for result in chunk_results])
        response = self.generate_completion(user_question, context_str)
        
        return {
            "response": response,
            "results": chunk_results,
            "intent_analysis": intent_analysis,
            "search_strategy": "full_pipeline"
        }

def init_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "feedback_data" not in st.session_state:
        st.session_state.feedback_data = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

def save_user_feedback(session, query: str, response: str, rating: int, comments: str = ""):
    """Save user feedback to Snowflake database."""
    try:
        feedback_data = pd.DataFrame([{
            'SESSION_ID': st.session_state.session_id,
            'QUERY_TEXT': query,
            'RESPONSE_TEXT': response,
            'USER_RATING': rating,
            'FEEDBACK_COMMENTS': comments,
            'TIMESTAMP': datetime.now(),
            'METADATA': json.dumps({
                'app_version': 'multi_stage_cuad_v1',
                'trulens_enabled': TRULENS_AVAILABLE
            })
        }])
        
        session.write_pandas(
            feedback_data,
            table_name="USER_FEEDBACK",
            database="AI_OBSERVABILITY_DB",
            schema="EVALUATION_SCHEMA",
            overwrite=False
        )
        return True
    except Exception as e:
        st.error(f"Error saving feedback: {e}")
        return False

def build_enhanced_references(results):
    """Build enhanced references with document grouping and chunk previews."""
    if not results:
        return ""
    
    document_chunks = {}
    for i, result in enumerate(results):
        if not isinstance(result, dict):
            continue
            
        filename = result.get('filename') or result.get('FILENAME')
        file_url = result.get('file_url') or result.get('FILE_URL')
        chunk_content = (result.get('contextualized_chunk') or
                        result.get('CONTEXTUALIZED_CHUNK') or
                        result.get('chunk') or
                        result.get('CHUNK'))
        
        if not filename:
            continue
            
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
            
        if chunk_content:
            clean_chunk = chunk_content.replace('\n', ' ').strip()
            chunk_preview = clean_chunk[:147] + "..." if len(clean_chunk) > 150 else clean_chunk
            
            if chunk_preview not in [chunk['preview'] for chunk in document_chunks[filename]['chunks']]:
                document_chunks[filename]['chunks'].append({
                    'preview': chunk_preview,
                    'index': i + 1
                })
    
    if not document_chunks:
        return ""
    
    sorted_docs = sorted(document_chunks.items(), key=lambda x: x[1]['first_seen_index'])
    references_md = "###### 📚 Sources & References\n\n"
    
    for filename, doc_info in sorted_docs:
        display_name = doc_info['display_name']
        file_url = doc_info['file_url']
        chunks = doc_info['chunks']
        
        if file_url:
            references_md += f"**📄 [{display_name}]({file_url})**\n"
        else:
            references_md += f"**📄 {display_name}**\n"
            
        if chunks:
            for chunk in chunks[:3]:  # Show up to 3 chunks per document
                references_md += f"- *Excerpt {chunk['index']}:* \"{chunk['preview']}\"\n"
        references_md += "\n"
    
    if len(sorted_docs) > 1:
        total_chunks = sum(len(doc_info['chunks']) for _, doc_info in sorted_docs)
        references_md += f"*📊 Total: {len(sorted_docs)} documents, {total_chunks} relevant excerpts*\n"
    
    return references_md

def display_feedback_form(query: str, response: str, message_idx: int):
    """Display user feedback form for a specific message."""
    with st.expander("📝 Provide Feedback", expanded=False):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            rating = st.select_slider(
                "Rate this response:",
                options=[1, 2, 3, 4, 5],
                value=3,
                format_func=lambda x: "⭐" * x,
                key=f"rating_{message_idx}"
            )
            
            comments = st.text_area(
                "Additional comments (optional):",
                placeholder="How can we improve this response?",
                key=f"comments_{message_idx}"
            )
        
        with col2:
            if st.button("Submit", key=f"submit_{message_idx}"):
                if save_user_feedback(session, query, response, rating, comments):
                    st.success("✅ Feedback saved!")
                    st.session_state.feedback_data.append({
                        'query': query,
                        'rating': rating,
                        'comments': comments,
                        'timestamp': datetime.now()
                    })

def display_evaluation_sidebar():
    """Display evaluation metrics and feedback summary in sidebar."""
    st.sidebar.markdown("## 📊 Evaluation Dashboard")
    
    # Feedback summary
    if st.session_state.feedback_data:
        ratings = [f['rating'] for f in st.session_state.feedback_data]
        avg_rating = sum(ratings) / len(ratings)
        
        st.sidebar.metric("Average Rating", f"{avg_rating:.1f}⭐")
        st.sidebar.metric("Total Feedback", len(ratings))
        
        # Rating distribution
        rating_counts = pd.Series(ratings).value_counts().sort_index()
        st.sidebar.bar_chart(rating_counts)
    
    # TruLens integration info
    st.sidebar.markdown("### 🔍 AI Observability")
    
    # Check if TruLens is properly registered
    trulens_status = st.session_state.get('trulens_registered', False)
    
    if TRULENS_AVAILABLE and trulens_status:
        st.sidebar.markdown("""
        ✅ **TruLens Active**: This session is being traced for:
        - Query intent analysis
        - Retrieval performance  
        - Response quality
        - User satisfaction
        
        📊 View detailed traces in **Snowsight → AI & ML → Evaluations**
        """)
    elif TRULENS_AVAILABLE:
        st.sidebar.markdown("""
        ⚠️ **TruLens Registration Failed**: Using basic tracing only.
        
        📝 **User feedback** and **local metrics** are still available.
        
        💡 **Tip**: Check Snowflake permissions for temporary stages.
        """)
    else:
        st.sidebar.markdown("""
        📊 **Basic Evaluation Mode**: 
        - User feedback collection active
        - Local performance metrics available
        
        🚀 **Install TruLens** for advanced observability:
        ```bash
        pip install trulens-core==1.5.2
        ```
        """)

def main():
    """Main Streamlit application with enhanced evaluation capabilities."""
    st.set_page_config(
        page_title="🤖 Intelligent RAG Chatbot with AI Observability",
        page_icon="🤖",
        layout="wide"
    )
    
    st.title("🤖 Intelligent Multi-Stage RAG Chatbot")
    
    # Dynamic caption based on TruLens status
    if TRULENS_AVAILABLE and st.session_state.get('trulens_registered', False):
        st.caption("🔍 **AI Observability Enabled** | Powered by Snowflake Cortex + TruLens")
    elif TRULENS_AVAILABLE:
        st.caption("📊 **Evaluation Mode** | Powered by Snowflake Cortex + User Feedback")
    else:
        st.caption("🚀 **Enhanced RAG** | Powered by Snowflake Cortex")
    
    # Initialize session state and get Snowflake session
    init_session_state()
    global session
    session = get_active_session()
    
    # Initialize instrumented RAG chatbot
    if "rag_chatbot" not in st.session_state:
        st.session_state.rag_chatbot = InstrumentedRAGChatbot(session)
        
        # Register with TruLens if available (optional - app works without it)
        if TRULENS_AVAILABLE:
            try:
                tru_connector = SnowflakeConnector(snowpark_session=session)
                st.session_state.tru_app = TruApp(
                    st.session_state.rag_chatbot,
                    app_name="intelligent_rag_chatbot",
                    app_version="streamlit_with_feedback",
                    connector=tru_connector
                )
                st.sidebar.success("✅ TruLens observability active")
                st.session_state.trulens_registered = True
            except Exception as e:
                st.sidebar.warning(f"⚠️ TruLens registration failed: {e}")
                st.sidebar.info("ℹ️ App continues to work with basic tracing only")
                st.session_state.trulens_registered = False
    
    # Display evaluation sidebar
    display_evaluation_sidebar()
    
    # Main chat interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Display chat messages
        for i, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # Add feedback form for assistant messages
                if message["role"] == "assistant" and "query" in message:
                    display_feedback_form(
                        message["query"], 
                        message["content"], 
                        i
                    )
        
        # Chat input
        if prompt := st.chat_input("Ask about legal contracts (e.g., 'Compare IP ownership in development vs endorsement agreements')"):
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate response
            with st.chat_message("assistant"):
                with st.spinner("🔍 Analyzing query and searching documents..."):
                    result = st.session_state.rag_chatbot.intelligent_search_orchestrator(prompt)
                
                # Display response
                st.markdown(result["response"])
                
                # Display enhanced references
                if result.get("results"):
                    references = build_enhanced_references(result["results"])
                    if references:
                        st.markdown(references)
                
                # Add to message history with query for feedback
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": result["response"],
                    "query": prompt,
                    "results": result.get("results", []),
                    "intent_analysis": result.get("intent_analysis", {}),
                    "search_strategy": result.get("search_strategy", "unknown")
                })
    
    with col2:
        # Query insights panel
        if st.session_state.messages:
            latest_message = st.session_state.messages[-1]
            if latest_message["role"] == "assistant" and "intent_analysis" in latest_message:
                st.markdown("### 🎯 Query Analysis")
                
                intent_data = latest_message["intent_analysis"]
                st.json(intent_data)
                
                st.markdown(f"**Search Strategy:** `{latest_message.get('search_strategy', 'unknown')}`")
                st.markdown(f"**Results Found:** {len(latest_message.get('results', []))}")
        
        # Sample queries
        st.markdown("### 💡 Sample Queries")
        sample_queries = [
            "What are the termination clauses in the NETGEAR distributor agreement?",
            "Compare IP ownership between development and endorsement agreements",
            "What governing law provisions are common across distribution agreements?",
            "How do renewal terms vary across different contract types?"
        ]
        
        for query in sample_queries:
            if st.button(query, key=f"sample_{hash(query)}"):
                st.session_state.messages.append({"role": "user", "content": query})
                st.rerun()

if __name__ == "__main__":
    main()
