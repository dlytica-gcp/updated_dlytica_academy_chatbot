from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
import tempfile
import os
from typing import List, Any, Dict, Optional
from langchain_core.documents import Document
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_vector_store(documents: List[Document], persist_directory: str = None) -> Chroma:
    """
    Create an optimized vector store from documents
    
    Args:
        documents: List of document chunks
        persist_directory: Directory to persist the vector store (optional)
        
    Returns:
        Chroma vector store instance
    """
    try:
        # Create a temporary directory if none provided
        if persist_directory is None:
            persist_directory = tempfile.mkdtemp()
        
        # Initialize embeddings with improved model
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-mpnet-base-v2",  # Using a more powerful embedding model
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True, 'batch_size': 32}  # Optimized batch processing
        )
        
        # Create vector store with optimized parameters
        vector_store = Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            persist_directory=persist_directory,
            collection_metadata={"hnsw:space": "cosine"}  # Explicitly use cosine similarity
        )
        
        # Persist the vector store
        vector_store.persist()
        
        logger.info(f"Created optimized vector store with {len(documents)} documents at {persist_directory}")
        return vector_store
        
    except Exception as e:
        logger.error(f"Error creating vector store: {str(e)}")
        raise

def setup_rag_chain(vector_store: Chroma, llm: Any) -> RetrievalQA:
    """
    Set up an enhanced retrieval QA chain with the vector store
    
    Args:
        vector_store: Chroma vector store instance
        llm: Language model instance
        
    Returns:
        Configured QA chain
    """
    try:
        # Set up retriever with optimized parameters
        retriever = vector_store.as_retriever(
            search_type="mmr",  # Use Maximum Marginal Relevance for diverse results
            search_kwargs={
                "k": 5,  # Retrieve top 5 chunks
                "fetch_k": 10,  # Fetch more, then select diverse subset
                "lambda_mult": 0.7  # Balance between relevance and diversity
            }
        )
        
        # Enhanced prompt template for more human-like responses
        qa_prompt_template = """
        You are Dlytica Academy's friendly and knowledgeable AI assistant. Your role is to provide accurate, helpful information about Dlytica, its programs, courses, and related topics. Answer the user's question based on the following context information.
         Donot try to force yourself to answer out of context questions. If they are out of context just tell the apologie to the user saying like sorry you are unaware of it or something like that.

        Context:
        {context}

        User Question: {question}

        Instructions:
        1. Answer in a conversational, warm tone - like a helpful academic advisor would speak.
        2. Be concise yet thorough in your explanations.Put the answer in summarized way so that the user could get the main point easily and try to not make the user bore with lengthy contents.
        3. If the context contains the information needed, provide a complete answer.
        4. If you're unsure or the context doesn't contain the relevant information, respond with: 
           "I don't have specific information about that aspect of Dlytica Academy. Would you like me to help you with something else about our programs?"
        5. Never invent information about Dlytica or its programs.
        6. Always stay factual and accurate to the provided information.
        7. Use natural language transitions rather than numbered points or bullet points when possible.
        8. For questions about enrollment, courses, or programs, provide any relevant details from the context.
        9. If the question is about Dlytica Academy but not covered in the context, you can acknowledge that it's about Dlytica but explain you don't have that specific information.

        Your response:
        """
                
        prompt = PromptTemplate(
            template=qa_prompt_template,
            input_variables=["context", "question"]
        )
        
        # Create enhanced QA chain with memory and citations
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",  # Using stuff chain for better context integration
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={
                "prompt": prompt,
                "verbose": True,  # Enable verbose mode for debugging
            }
        )
        
        # Test the chain with a harmless query
        test_query = "What is Dlytica Academy?"
        test_response = qa_chain.invoke({"query": test_query})
        
        if not test_response:
            raise ValueError("Failed to initialize QA chain")
            
        logger.info("Enhanced RAG chain initialized successfully")
        return qa_chain

# def setup_rag_chain(vector_store: Chroma, llm: Any) -> RetrievalQA:
#     try:
#         retriever = vector_store.as_retriever(
#         search_type="mmr",  # Maximum Marginal Relevance for diversity
#         search_kwargs={
#             "k": 5,  # Retrieve top 5 documents
#             "fetch_k": 10,  # Fetch more, then select diverse subset
#             "lambda_mult": 0.7,  # Balance between relevance and diversity
#         }
#         )

#     # Custom retrieval filtering function
#         def filter_relevant_documents(documents: List[Document]) -> List[Document]:
#             """
#             Filter documents that contain the word 'dlytica' in their content.
#             This is a simple check to ensure only relevant documents are used.
#             """
#             return [doc for doc in documents if 'dlytica' in doc.page_content.lower()]

#         # Modify retriever to manually filter the documents after retrieval
#         def custom_retrieve(query: str) -> List[Document]:
#             # First, retrieve documents using the retriever
#             documents = retriever.retrieve(query)

#             # Apply the custom filtering function to the retrieved documents
#             relevant_documents = filter_relevant_documents(documents)

#             return relevant_documents

#         # Set up the RAG chain with the custom retriever
#         qa_chain = RetrievalQA.from_chain_type(
#             llm=llm,
#             chain_type="stuff",  # Stuff chain for better context integration
#             retriever=custom_retrieve,
#             return_source_documents=True,
#             chain_type_kwargs={"verbose": True}
#         )

#         # Test the chain with a harmless query
#         test_query = "What is Dlytica Academy?"
#         test_response = qa_chain.invoke({"query": test_query})

#         if not test_response:
#             raise ValueError("Failed to initialize QA chain")
        
#         logger.info("Enhanced RAG chain initialized successfully")
#         return qa_chain
            
#     except Exception as e:
#         logger.error(f"Error setting up RAG chain: {str(e)}")
#         raise

# def format_docs(docs: List[Document]) -> str:
#     """
#     Enhanced helper function to format documents for context
#     with better delineation between documents
#     """
#     formatted_docs = []
    
#     for i, doc in enumerate(docs):
#         # Extract page number or source if available
#         source_info = f"Document {i+1}"
#         if hasattr(doc, 'metadata') and doc.metadata:
#             if 'source' in doc.metadata:
#                 source_info = f"From: {doc.metadata['source']}"
#             if 'page' in doc.metadata:
#                 source_info += f", Page: {doc.metadata['page']}"
                
#         # Format the document with source information
#         formatted_docs.append(f"{source_info}\n{doc.page_content.strip()}")
    
#     return "\n\n---\n\n".join(formatted_docs)

# def answer_question(query: str, qa_chain: RetrievalQA) -> Dict[str, Any]:
#     """
#     Enhanced function to answer questions with better error handling
    
#     Args:
#         query: User question
#         qa_chain: The QA chain to use
        
#     Returns:
#         dict: Response with answer and source documents
#     """
#     try:
#         # Pre-process the query to improve retrieval
#         processed_query = preprocess_query(query)
        
#         # Get response from the chain
#         response = qa_chain.invoke({"query": processed_query})
        
#         # Post-process the response
#         result = postprocess_response(response["result"])
        
#         return {
#             "result": result,
#             "source_documents": response.get("source_documents", []),
#             "query": query,
#             "processed_query": processed_query
#         }
    except Exception as e:
        logger.error(f"Error answering question: {str(e)}")
        return {
            "result": "I apologize, but I'm having trouble processing your question right now. Could you please try asking in a different way?",
            "error": str(e)
        }

def preprocess_query(query: str) -> str:
    """
    Preprocess user query to improve retrieval quality
    
    Args:
        query: Original user query
        
    Returns:
        str: Processed query
    """
    # Convert to lowercase
    query = query.lower()
    
    # Add Dlytica-specific context if needed
    if "dlytica" not in query and any(keyword in query for keyword in ["course", "program", "class", "academy", "training", "learn", "study", "enroll"]):
        query = f"dlytica academy {query}"
    
    return query

def postprocess_response(response: str) -> str:
    """
    Post-process the LLM response to improve readability and tone
    
    Args:
        response: Raw LLM response
        
    Returns:
        str: Processed response
    """
    # Remove any phrases that break immersion
    phrases_to_remove = [
        "based on the context",
        "according to the provided information",
        "based on the provided context",
        "from the context provided",
        "the context mentions",
        "based on the document"
    ]
    
    processed = response
    for phrase in phrases_to_remove:
        processed = processed.replace(phrase, "")
    
    # Clean up extra whitespace
    processed = " ".join(processed.split())
    
    return processed