"""
Base Memory Connector Interface

Defines the interface that all memory connectors must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path


class BaseMemoryConnector(ABC):
    """Base class for all memory connectors."""
    
    def __init__(self, output_path: str, **kwargs):
        """
        Initialize the connector.
        
        Args:
            output_path: Path where the organized memory will be stored
            **kwargs: Connector-specific configuration options
        """
        self.output_path = Path(output_path)
        self.config = kwargs
    
    @abstractmethod
    def extract_data(self, source_path: str) -> Dict[str, Any]:
        """
        Extract data from the source.
        
        Args:
            source_path: Path to the source data
            
        Returns:
            Dict containing extracted and parsed data
        """
        pass
    
    @abstractmethod
    def organize_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Organize the extracted data into topics and categories.
        
        Args:
            extracted_data: Raw extracted data
            
        Returns:
            Dict containing organized data structure
        """
        pass
    
    @abstractmethod
    def generate_memory_files(self, organized_data: Dict[str, Any]) -> None:
        """
        Generate memory files in the mem-agent format.
        
        Args:
            organized_data: Organized data structure
        """
        pass
    
    def connect(self, source_path: str, max_items: Optional[int] = None) -> None:
        """
        Complete connector workflow: extract, organize, and generate files.
        
        Args:
            source_path: Path to the source data
            max_items: Optional limit on number of items to process
        """
        print(f"🔌 Connecting {self.__class__.__name__} from {source_path}")
        
        # Step 1: Extract data
        print("📤 Extracting data...")
        extracted_data = self.extract_data(source_path)
        
        # Apply max_items limit if specified
        if max_items and 'items' in extracted_data:
            extracted_data['items'] = extracted_data['items'][:max_items]
            print(f"⚡ Limited to {max_items} items")
        
        # Step 2: Organize data
        print("🗂️  Organizing data...")
        organized_data = self.organize_data(extracted_data)
        
        # Step 3: Generate memory files
        print("📝 Generating memory files...")
        self.generate_memory_files(organized_data)
        
        print(f"✅ Memory connector completed! Output: {self.output_path}")
    
    def ensure_output_dir(self) -> None:
        """Ensure output directory exists."""
        self.output_path.mkdir(parents=True, exist_ok=True)
    
    @property
    @abstractmethod
    def connector_name(self) -> str:
        """Human-readable name of the connector."""
        pass
    
    @property
    @abstractmethod
    def supported_formats(self) -> list:
        """List of supported source formats/extensions."""
        pass