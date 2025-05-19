import os
import re
import logging
from typing import List, Dict, Any, Optional, Union
from langchain_community.document_loaders import (
    PyPDFLoader, 
    DirectoryLoader, 
    TextLoader, 
    CSVLoader,
    Docx2txtLoader,
    UnstructuredMarkdownLoader,
    UnstructuredExcelLoader
)
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter
)
from langchain_core.documents import Document

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_loader_for_file(file_path: str) -> Any:
    """
    Get the appropriate loader based on file extension
    
    Args:
        file_path: Path to the file
        
    Returns:
        The loader instance
    """
    file_extension = os.path.splitext(file_path)[1].lower()
    
    if file_extension == '.pdf':
        return PyPDFLoader(file_path)
    elif file_extension == '.txt':
        return TextLoader(file_path, encoding='utf8')
    elif file_extension == '.csv':
        return CSVLoader(file_path)
    elif file_extension in ['.docx', '.doc']:
        return Docx2txtLoader(file_path)
    elif file_extension in ['.md', '.markdown']:
        return UnstructuredMarkdownLoader(file_path)
    elif file_extension in ['.xlsx', '.xls']:
        return UnstructuredExcelLoader(file_path)
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

def clean_text(text: str) -> str:
    """
    Clean text by removing extra whitespace, fixing common OCR errors
    
    Args:
        text: Raw text
        
    Returns:
        Cleaned text
    """
    # Remove excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Fix common OCR errors
    text = text.replace('|', 'I')
    text = text.replace('l1', 'h')
    
    # Remove page numbers
    text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
    
    # Fix spacing issues
    text = re.sub(r'(?<=[.,;:!?])(?=[^\s])', ' ', text)
    
    return text.strip()

def enhance_metadata(doc: Document, file_path: str) -> Document:
    """
    Enhance document metadata with additional context
    
    Args:
        doc: Original document
        file_path: Path to the source file
        
    Returns:
        Document with enhanced metadata
    """
    # Preserve existing metadata
    metadata = doc.metadata.copy() if hasattr(doc, 'metadata') else {}
    
    # Add file info
    metadata['source'] = os.path.basename(file_path)
    metadata['file_path'] = file_path
    metadata['file_type'] = os.path.splitext(file_path)[1].lower()
    
    # Detect if content seems to be about specific topics
    content = doc.page_content.lower()
    
    if 'course' in content or 'program' in content:
        metadata['content_type'] = 'program_info'
    elif 'faq' in content or 'question' in content:
        metadata['content_type'] = 'faq'
    elif 'contact' in content or 'email' in content or 'phone' in content:
        metadata['content_type'] = 'contact_info'
    
    # Set the enhanced metadata
    doc.metadata = metadata
    
    return doc

def determine_optimal_chunk_size(text: str) -> int:
    """
    Determine the optimal chunk size based on document characteristics
    
    Args:
        text: Document text
        
    Returns:
        Optimal chunk size
    """
    # Start with base size
    base_size = 1000
    
    # Adjust based on document length
    if len(text) > 50000:  # Long document
        return base_size - 200  # Smaller chunks for long docs
    elif len(text) < 5000:  # Short document
        return base_size + 200  # Larger chunks to maintain context
    
    # Check for structured content
    if text.count('\n\n') > text.count('.') / 5:
        # Lots of paragraph breaks - structured content
        return base_size - 100
    
    return base_size

def load_documents(file_path: str) -> List[Document]:
    """
    Enhanced document loading with intelligent chunking
    
    Args:
        file_path: Path to document or directory
        
    Returns:
        List of document chunks with enhanced metadata
    """
    try:
        documents = []
        
        # Handle directory case
        if os.path.isdir(file_path):
            logger.info(f"Loading documents from directory: {file_path}")
            # Process each file in directory with appropriate loader
            for root, _, files in os.walk(file_path):
                for file in files:
                    full_path = os.path.join(root, file)
                    try:
                        file_docs = load_single_document(full_path)
                        documents.extend(file_docs)
                    except Exception as e:
                        logger.warning(f"Error loading {full_path}: {str(e)}")
        else:
            # Handle single file
            logger.info(f"Loading document: {file_path}")
            documents = load_single_document(file_path)
        
        if not documents:
            raise ValueError(f"No content found in: {file_path}")
        
        logger.info(f"Loaded {len(documents)} document chunks successfully")
        return documents
        
    except Exception as e:
        logger.error(f"Error loading documents: {str(e)}")
        raise

def load_single_document(file_path: str) -> List[Document]:
    """
    Load and process a single document file
    
    Args:
        file_path: Path to the document
        
    Returns:
        List of document chunks
    """
    # Get appropriate loader
    loader = get_loader_for_file(file_path)
    
    # Load raw documents
    raw_documents = loader.load()
    
    if not raw_documents:
        logger.warning(f"No content found in: {file_path}")
        return []
    
    # Clean and enhance documents
    enhanced_docs = []
    for doc in raw_documents:
        # Clean text
        doc.page_content = clean_text(doc.page_content)
        
        # Enhance metadata
        doc = enhance_metadata(doc, file_path)
        
        if doc.page_content.strip():  # Only add non-empty documents
            enhanced_docs.append(doc)
    
    # Get sample text to determine optimal chunk size
    sample_text = " ".join([doc.page_content for doc in enhanced_docs[:3]])
    chunk_size = determine_optimal_chunk_size(sample_text)
    
    # Special handling for markdown
    if file_path.endswith(('.md', '.markdown')):
        return split_markdown_documents(enhanced_docs)
    
    # Split documents
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=True
    )
    
    split_docs = text_splitter.split_documents(enhanced_docs)
    
    logger.info(f"Split {len(enhanced_docs)} documents into {len(split_docs)} chunks with size {chunk_size}")
    
    return split_docs

def split_markdown_documents(docs: List[Document]) -> List[Document]:
    """
    Special handling for markdown documents to preserve structure
    
    Args:
        docs: List of markdown documents
        
    Returns:
        Split documents preserving header structure
    """
    # Define markdown headers to split on
    headers_to_split_on = [
        ("#", "header1"),
        ("##", "header2"),
        ("###", "header3"),
        ("####", "header4"),
    ]
    
    # Initialize markdown splitter
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on
    )
    
    split_docs = []
    
    # Process each document
    for doc in docs:
        # Split based on markdown headers
        header_splits = markdown_splitter.split_text(doc.page_content)
        
        # Preserve metadata
        for split in header_splits:
            # Merge original metadata with header metadata
            combined_metadata = {**doc.metadata, **split.metadata}
            split.metadata = combined_metadata
            split_docs.append(split)
    
    # Further split if chunks are too large
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
        keep_separator=True
    )
    
    return text_splitter.split_documents(split_docs)