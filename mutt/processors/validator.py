"""
Validator processor for Mutt message processing pipeline.
Validates incoming messages for required fields and data integrity.
"""

from typing import List
from mutt.models.message import Message


class Validator:
    """
    Validates Message objects for required fields and data integrity.
    
    The validator checks for:
    - Presence of source_ip
    - Non-empty payload
    - Any other validation rules as needed
    
    Validation errors are stored in msg.metadata["validation_errors"].
    """
    
    def validate(self, msg: Message) -> bool:
        """
        Validate a Message object.
        
        Args:
            msg: The Message object to validate
            
        Returns:
            bool: True if the message is valid, False otherwise
            
        Side Effects:
            Adds validation errors to msg.metadata["validation_errors"]
            if the message is invalid.
        """
        # Initialize validation errors list if it doesn't exist
        if "validation_errors" not in msg.metadata:
            msg.metadata["validation_errors"] = []
        
        errors: List[str] = []
        
        # Check if source_ip is present
        if not msg.source_ip:
            errors.append("Missing required field: source_ip")
        
        # Check if payload is not empty
        if not msg.payload:
            errors.append("Payload cannot be empty")
        
        # Add errors to metadata if any were found
        if errors:
            msg.metadata["validation_errors"].extend(errors)
            return False
        
        return True
