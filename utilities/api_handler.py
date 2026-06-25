# utilities/api_handler.py
"""
API Handler Module for Task 9: AI Model Integration and API Development
Handles API endpoints for text summarization with proper error handling and logging.
"""
import json
import time
import logging
from typing import Dict, Any, Optional
from flask import request, jsonify
from datetime import datetime

from .ai_model import get_ai_summarizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class APIRequestHandler:
    """
    Handles API requests for text summarization with validation and error handling.
    """
    
    def __init__(self):
        self.ai_summarizer = get_ai_summarizer()
        self.request_log = []
        self.max_request_size = 10 * 1024 * 1024  # 10MB
        self.request_timeout = 300  # 5 minutes
        
    def validate_request(self, data: Dict) -> tuple[bool, Optional[str], Optional[Dict]]:
        """
        Validate API request parameters.
        
        Args:
            data: Request data dictionary
            
        Returns:
            Tuple of (is_valid, error_message, validated_data)
        """
        try:
            # Check required fields
            if 'text' not in data:
                return False, "Missing required field: 'text'", None
            
            text = data['text']
            
            # Validate text
            if not isinstance(text, str):
                return False, "Field 'text' must be a string", None
            
            if not text.strip():
                return False, "Text cannot be empty", None
            
            # Check text size
            text_size = len(text.encode('utf-8'))
            if text_size > self.max_request_size:
                return False, f"Text too large ({text_size:,} bytes). Maximum is {self.max_request_size:,} bytes.", None
            
            # Validate optional parameters
            validated_data = {'text': text.strip()}
            
            # Compression ratio
            if 'compression_ratio' in data:
                try:
                    ratio = float(data['compression_ratio'])
                    if not 0.1 <= ratio <= 0.8:
                        return False, "compression_ratio must be between 0.1 and 0.8", None
                    validated_data['compression_ratio'] = ratio
                except (ValueError, TypeError):
                    return False, "compression_ratio must be a number", None
            else:
                validated_data['compression_ratio'] = 0.3
            
            # Max length
            if 'max_length' in data:
                try:
                    max_len = int(data['max_length'])
                    if not 10 <= max_len <= 500:
                        return False, "max_length must be between 10 and 500", None
                    validated_data['max_length'] = max_len
                except (ValueError, TypeError):
                    return False, "max_length must be an integer", None
            
            # Min length
            if 'min_length' in data:
                try:
                    min_len = int(data['min_length'])
                    if not 5 <= min_len <= 200:
                        return False, "min_length must be between 5 and 200", None
                    validated_data['min_length'] = min_len
                except (ValueError, TypeError):
                    return False, "min_length must be an integer", None
            
            # Language (optional)
            if 'language' in data:
                lang = str(data['language']).strip().lower()
                if lang not in ['en', 'fr', 'de', 'es', 'it', 'pt', 'nl', 'ru']:
                    logger.warning(f"Unsupported language requested: {lang}")
                validated_data['language'] = lang
            
            return True, None, validated_data
            
        except Exception as e:
            logger.error(f"Validation error: {str(e)}")
            return False, f"Validation error: {str(e)[:100]}", None
    
    def log_request(self, request_data: Dict, response_data: Dict, processing_time: float):
        """
        Log API request for monitoring and optimization.
        
        Args:
            request_data: Original request data
            response_data: API response data
            processing_time: Time taken to process request
        """
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'endpoint': request.path if request else 'unknown',
            'method': request.method if request else 'unknown',
            'text_length': len(request_data.get('text', '').split()) if 'text' in request_data else 0,
            'compression_ratio': request_data.get('compression_ratio', 0.3),
            'processing_time': round(processing_time, 2),
            'success': response_data.get('success', False),
            'summary_length': response_data.get('summary_length', 0),
            'error': response_data.get('error') if not response_data.get('success') else None
        }
        
        self.request_log.append(log_entry)
        
        # Keep only last 1000 logs
        if len(self.request_log) > 1000:
            self.request_log = self.request_log[-1000:]
        
        # Log to file/system log
        log_message = (f"API Request: {log_entry['endpoint']} - "
                      f"{log_entry['text_length']} words - "
                      f"{log_entry['processing_time']}s - "
                      f"{'SUCCESS' if log_entry['success'] else 'FAILED'}")
        
        if log_entry['success']:
            logger.info(log_message)
        else:
            logger.warning(f"{log_message} - Error: {log_entry['error']}")
    
    def handle_summarize_request(self) -> Dict:
        """
        Handle summarization API request with timeout and error handling.
        
        Returns:
            Dictionary with API response
        """
        start_time = time.time()
        request_id = f"req_{int(start_time)}_{hash(str(start_time)) % 10000:04d}"
        
        logger.info(f"Starting request {request_id}")
        
        try:
            # Parse request data
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form.to_dict()
                
                # If text is in files, read it
                if 'file' in request.files:
                    file = request.files['file']
                    text = file.read().decode('utf-8', errors='ignore')
                    data['text'] = text
            
            # Validate request
            is_valid, error_msg, validated_data = self.validate_request(data)
            
            if not is_valid:
                response = {
                    'success': False,
                    'error': error_msg,
                    'request_id': request_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
                self.log_request(data, response, time.time() - start_time)
                return response
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > self.request_timeout:
                response = {
                    'success': False,
                    'error': f'Request timeout after {elapsed:.1f}s',
                    'request_id': request_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
                self.log_request(validated_data, response, elapsed)
                return response
            
            # Prepare summarization parameters
            summarization_params = {
                'compression_ratio': validated_data['compression_ratio']
            }
            
            # Add optional parameters if provided
            optional_params = ['max_length', 'min_length', 'language']
            for param in optional_params:
                if param in validated_data:
                    summarization_params[param] = validated_data[param]
            
            # Perform summarization
            logger.info(f"Request {request_id}: Summarizing {validated_data['text_length']} words")
            
            result = self.ai_summarizer.summarize_text(
                validated_data['text'],
                **summarization_params
            )
            
            # Add request metadata to result
            result['request_id'] = request_id
            result['timestamp'] = datetime.utcnow().isoformat()
            result['processing_time'] = round(time.time() - start_time, 2)
            result['model_used'] = self.ai_summarizer.model_name
            
            # Log the request
            self.log_request(validated_data, result, result['processing_time'])
            
            logger.info(f"Request {request_id} completed in {result['processing_time']}s")
            
            return result
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON: {str(e)}"
            logger.error(f"Request {request_id} - {error_msg}")
            
            response = {
                'success': False,
                'error': error_msg,
                'request_id': request_id,
                'timestamp': datetime.utcnow().isoformat()
            }
            self.log_request({}, response, time.time() - start_time)
            return response
            
        except Exception as e:
            error_msg = f"Internal server error: {str(e)[:200]}"
            logger.error(f"Request {request_id} - {error_msg}", exc_info=True)
            
            response = {
                'success': False,
                'error': error_msg,
                'request_id': request_id,
                'timestamp': datetime.utcnow().isoformat()
            }
            self.log_request({}, response, time.time() - start_time)
            return response
    
    def get_api_stats(self) -> Dict:
        """
        Get API statistics for monitoring.
        
        Returns:
            Dictionary with API statistics
        """
        if not self.request_log:
            return {
                'total_requests': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'avg_processing_time': 0,
                'recent_requests': []
            }
        
        total = len(self.request_log)
        successful = sum(1 for req in self.request_log if req['success'])
        failed = total - successful
        
        # Calculate average processing time for successful requests
        successful_times = [req['processing_time'] for req in self.request_log if req['success']]
        avg_time = sum(successful_times) / len(successful_times) if successful_times else 0
        
        # Get recent requests (last 10)
        recent = self.request_log[-10:] if len(self.request_log) >= 10 else self.request_log
        
        return {
            'total_requests': total,
            'successful_requests': successful,
            'failed_requests': failed,
            'success_rate': round(successful / total * 100, 1) if total > 0 else 0,
            'avg_processing_time': round(avg_time, 2),
            'total_words_processed': sum(req['text_length'] for req in self.request_log),
            'ai_model_stats': self.ai_summarizer.get_performance_stats(),
            'recent_requests': recent
        }


# Global API handler instance
_api_handler_instance = None

def get_api_handler() -> APIRequestHandler:
    """
    Factory function to get or create API handler instance.
    
    Returns:
        APIRequestHandler instance
    """
    global _api_handler_instance
    
    if _api_handler_instance is None:
        _api_handler_instance = APIRequestHandler()
    
    return _api_handler_instance


def create_summarize_endpoint():
    """
    Create Flask endpoint for text summarization.
    
    Returns:
        Flask response
    """
    api_handler = get_api_handler()
    response = api_handler.handle_summarize_request()
    
    # Convert to Flask response
    status_code = 200 if response['success'] else 400
    
    # Remove internal fields before sending response
    response_to_send = response.copy()
    
    return jsonify(response_to_send), status_code


def create_stats_endpoint():
    """
    Create Flask endpoint for API statistics.
    
    Returns:
        Flask response with statistics
    """
    api_handler = get_api_handler()
    stats = api_handler.get_api_stats()
    
    return jsonify({
        'success': True,
        'stats': stats,
        'timestamp': datetime.utcnow().isoformat()
    }), 200


def create_health_endpoint():
    """
    Create Flask health check endpoint.
    
    Returns:
        Flask response with health status
    """
    api_handler = get_api_handler()
    
    # Check if AI model is loaded
    model_loaded = api_handler.ai_summarizer.is_loaded
    
    health_status = {
        'status': 'healthy' if model_loaded else 'degraded',
        'timestamp': datetime.utcnow().isoformat(),
        'model_loaded': model_loaded,
        'total_requests': len(api_handler.request_log),
        'memory_usage': 'N/A'  # Could add psutil for memory monitoring
    }
    
    status_code = 200 if model_loaded else 503
    
    return jsonify(health_status), status_code


# Test function for module verification
def test_api_module():
    """Test function to verify the API module works correctly."""
    print("=" * 60)
    print("Testing API Handler Module")
    print("=" * 60)
    
    try:
        # Create API handler
        api_handler = APIRequestHandler()
        
        # Test validation
        print("1. Testing request validation...")
        
        # Test valid request
        valid_data = {
            'text': 'This is a test text for summarization. ' * 10,
            'compression_ratio': 0.3
        }
        
        is_valid, error, validated = api_handler.validate_request(valid_data)
        if is_valid:
            print("   ✅ Valid request accepted")
        else:
            print(f"   ❌ Valid request rejected: {error}")
            return False
        
        # Test invalid request (missing text)
        invalid_data = {'compression_ratio': 0.3}
        is_valid, error, validated = api_handler.validate_request(invalid_data)
        if not is_valid:
            print("   ✅ Invalid request correctly rejected")
        else:
            print("   ❌ Invalid request incorrectly accepted")
            return False
        
        # Test invalid compression ratio
        invalid_ratio = {'text': 'test', 'compression_ratio': 2.0}
        is_valid, error, validated = api_handler.validate_request(invalid_ratio)
        if not is_valid:
            print("   ✅ Invalid compression ratio rejected")
        else:
            print("   ❌ Invalid compression ratio accepted")
            return False
        
        # Test logging
        print("\n2. Testing request logging...")
        test_response = {
            'success': True,
            'summary_length': 50,
            'error': None
        }
        
        api_handler.log_request(valid_data, test_response, 1.5)
        print(f"   ✅ Request logged (total: {len(api_handler.request_log)})")
        
        # Test stats
        print("\n3. Testing statistics...")
        stats = api_handler.get_api_stats()
        print(f"   ✅ Statistics collected")
        print(f"   Total requests: {stats['total_requests']}")
        print(f"   Success rate: {stats['success_rate']}%")
        
        print("\n" + "=" * 60)
        print("✅ API Handler Module Test PASSED")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ API Module Test FAILED: {str(e)}")
        return False


if __name__ == "__main__":
    # Run test if module is executed directly
    test_api_module()