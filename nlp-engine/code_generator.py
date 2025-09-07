"""
Enhanced Code Generation Engine
Uses transformer models and template-based generation for code creation
"""

import re
import ast
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logging.warning("Transformers library not available. Code generation will use templates only.")

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class CodeTemplate:
    """Template for code generation"""
    name: str
    language: str
    template: str
    description: str
    variables: List[str]


class CodeGenerator:
    """Enhanced code generation without OpenAI dependency"""
    
    def __init__(self):
        self.templates = self._load_templates()
        self.code_model = self._load_code_model() if TRANSFORMERS_AVAILABLE else None
    
    def _load_code_model(self):
        """Load a code generation model"""
        try:
            # Use CodeT5 or similar smaller code generation model
            # These are much smaller than GPT models but still effective for basic code gen
            model_name = "Salesforce/codet5-small"
            
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForCausalLM.from_pretrained(model_name)
            
            code_generator = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_length=200,
                temperature=0.3,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )
            
            logger.info("Loaded CodeT5 model for code generation")
            return code_generator
            
        except Exception as e:
            logger.warning(f"Failed to load code generation model: {e}")
            return None
    
    def _load_templates(self) -> Dict[str, List[CodeTemplate]]:
        """Load code templates by language"""
        return {
            "python": [
                CodeTemplate(
                    name="function",
                    language="python",
                    template='''def {function_name}({parameters}):
    """
    {description}
    
    Args:
        {args_docs}
    
    Returns:
        {return_type}: {return_description}
    """
    {body}
''',
                    description="Python function template",
                    variables=["function_name", "parameters", "description", "args_docs", "return_type", "return_description", "body"]
                ),
                CodeTemplate(
                    name="class",
                    language="python",
                    template='''class {class_name}:
    """
    {description}
    """
    
    def __init__(self{init_params}):
        """Initialize {class_name}."""
        {init_body}
    
    {methods}
''',
                    description="Python class template",
                    variables=["class_name", "description", "init_params", "init_body", "methods"]
                ),
                CodeTemplate(
                    name="validation_function",
                    language="python",
                    template='''def validate_{field_name}({field_name}):
    """
    Validate {field_name} input.
    
    Args:
        {field_name}: The {field_name} to validate
    
    Returns:
        bool: True if valid, False otherwise
    """
    if not {field_name}:
        return False
    
    {validation_logic}
    
    return True
''',
                    description="Input validation function",
                    variables=["field_name", "validation_logic"]
                ),
                CodeTemplate(
                    name="api_endpoint",
                    language="python",
                    template='''@app.route("/{endpoint}", methods=["{method}"])
def {function_name}():
    """
    {description}
    """
    try:
        {request_handling}
        
        {business_logic}
        
        return jsonify({{"status": "success", "data": result}})
    
    except Exception as e:
        logger.error(f"Error in {function_name}: {{e}}")
        return jsonify({{"status": "error", "message": str(e)}}), 500
''',
                    description="Flask API endpoint template",
                    variables=["endpoint", "method", "function_name", "description", "request_handling", "business_logic"]
                )
            ],
            "javascript": [
                CodeTemplate(
                    name="function",
                    language="javascript",
                    template='''function {function_name}({parameters}) {{
    /**
     * {description}
     * {param_docs}
     * @returns {{{return_type}}} {return_description}
     */
    {body}
}}
''',
                    description="JavaScript function template",
                    variables=["function_name", "parameters", "description", "param_docs", "return_type", "return_description", "body"]
                ),
                CodeTemplate(
                    name="class",
                    language="javascript",
                    template='''class {class_name} {{
    /**
     * {description}
     */
    
    constructor({constructor_params}) {{
        {constructor_body}
    }}
    
    {methods}
}}
''',
                    description="JavaScript class template",
                    variables=["class_name", "description", "constructor_params", "constructor_body", "methods"]
                ),
                CodeTemplate(
                    name="async_function",
                    language="javascript",
                    template='''async function {function_name}({parameters}) {{
    /**
     * {description}
     * {param_docs}
     * @returns {{Promise<{return_type}>}} {return_description}
     */
    try {{
        {body}
    }} catch (error) {{
        console.error(`Error in {function_name}:`, error);
        throw error;
    }}
}}
''',
                    description="Async JavaScript function template",
                    variables=["function_name", "parameters", "description", "param_docs", "return_type", "return_description", "body"]
                )
            ],
            "java": [
                CodeTemplate(
                    name="method",
                    language="java",
                    template='''/**
 * {description}
 * {param_docs}
 * @return {return_description}
 */
public {return_type} {method_name}({parameters}) {{
    {body}
}}
''',
                    description="Java method template",
                    variables=["description", "param_docs", "return_description", "return_type", "method_name", "parameters", "body"]
                ),
                CodeTemplate(
                    name="class",
                    language="java",
                    template='''/**
 * {description}
 */
public class {class_name} {{
    
    {fields}
    
    /**
     * Constructor for {class_name}.
     */
    public {class_name}({constructor_params}) {{
        {constructor_body}
    }}
    
    {methods}
}}
''',
                    description="Java class template",
                    variables=["description", "class_name", "fields", "constructor_params", "constructor_body", "methods"]
                )
            ]
        }
    
    def generate_code(self, description: str, language: str = "python", 
                     code_type: str = "function", context: Dict = None) -> str:
        """Generate code based on description and requirements"""
        
        # First try transformer-based generation if available
        if self.code_model and settings.enable_transformers:
            try:
                transformer_code = self._generate_with_transformer(description, language, code_type)
                if transformer_code and len(transformer_code.strip()) > 20:
                    return transformer_code
            except Exception as e:
                logger.warning(f"Transformer generation failed: {e}")
        
        # Fallback to template-based generation
        return self._generate_with_template(description, language, code_type, context or {})
    
    def _generate_with_transformer(self, description: str, language: str, code_type: str) -> Optional[str]:
        """Generate code using transformer model"""
        if not self.code_model:
            return None
        
        # Create a prompt for code generation
        prompt = f"# {language.title()} {code_type}\n# {description}\n"
        
        # Add language-specific starter
        if language == "python":
            if code_type == "function":
                prompt += "def "
            elif code_type == "class":
                prompt += "class "
        elif language == "javascript":
            if code_type == "function":
                prompt += "function "
            elif code_type == "class":
                prompt += "class "
        elif language == "java":
            if code_type == "method":
                prompt += "public "
            elif code_type == "class":
                prompt += "public class "
        
        try:
            # Generate code
            result = self.code_model(prompt, max_length=150, num_return_sequences=1)
            generated_text = result[0]['generated_text']
            
            # Extract the generated part (remove the prompt)
            generated_code = generated_text[len(prompt):].strip()
            
            return generated_code
            
        except Exception as e:
            logger.error(f"Error in transformer generation: {e}")
            return None
    
    def _generate_with_template(self, description: str, language: str, 
                               code_type: str, context: Dict) -> str:
        """Generate code using templates"""
        
        if language not in self.templates:
            language = "python"  # Default fallback
        
        # Find appropriate template
        template = None
        for tmpl in self.templates[language]:
            if tmpl.name == code_type or code_type in tmpl.name:
                template = tmpl
                break
        
        if not template:
            # Use first available template
            template = self.templates[language][0]
        
        # Extract information from description
        extracted_info = self._extract_code_info(description, language, code_type)
        
        # Merge with context
        variables = {**extracted_info, **context}
        
        # Fill template
        try:
            return template.template.format(**variables)
        except KeyError as e:
            logger.warning(f"Missing template variable {e}, using placeholder")
            # Fill missing variables with placeholders
            for var in template.variables:
                if var not in variables:
                    variables[var] = f"# TODO: {var}"
            
            return template.template.format(**variables)
    
    def _extract_code_info(self, description: str, language: str, code_type: str) -> Dict[str, str]:
        """Extract code information from description"""
        info = {}
        desc_lower = description.lower()
        
        # Extract function/class name
        name_patterns = [
            r'(?:function|method|class)\s+(?:called|named)\s+(\w+)',
            r'(?:create|add|implement)\s+(?:a\s+)?(\w+)\s+(?:function|method|class)',
            r'(\w+)\s+(?:function|method|class)',
            r'(?:function|method|class)\s+(\w+)'
        ]
        
        name = None
        for pattern in name_patterns:
            match = re.search(pattern, desc_lower)
            if match:
                name = match.group(1)
                break
        
        if not name:
            # Generate generic name based on description words
            words = re.findall(r'\b\w+\b', desc_lower)
            if words:
                name = '_'.join(words[:3])  # Use first 3 words
            else:
                name = f"generated_{code_type}"
        
        info['function_name'] = name
        info['method_name'] = name  
        info['class_name'] = name.title().replace('_', '')
        
        # Extract parameters
        param_patterns = [
            r'(?:takes?|accepts?|with)\s+(?:parameters?|args?|arguments?)\s+(.*?)(?:\.|$)',
            r'(?:parameters?|args?)\s*:?\s*(.*?)(?:\.|$)'
        ]
        
        parameters = ""
        for pattern in param_patterns:
            match = re.search(pattern, desc_lower)
            if match:
                param_text = match.group(1).strip()
                # Simple parameter parsing
                if ',' in param_text:
                    params = [p.strip() for p in param_text.split(',')]
                    parameters = ", ".join(params)
                else:
                    parameters = param_text
                break
        
        if not parameters and "email" in desc_lower:
            parameters = "email"
        elif not parameters and "password" in desc_lower:
            parameters = "password"
        elif not parameters and "user" in desc_lower:
            parameters = "user_data"
        
        info['parameters'] = parameters
        info['constructor_params'] = parameters
        
        # Set description
        info['description'] = description
        
        # Generate body based on description keywords
        body = self._generate_function_body(description, language)
        info['body'] = body
        info['init_body'] = "pass" if language == "python" else ""
        info['constructor_body'] = ""
        
        # Default values for other template variables
        info.update({
            'args_docs': self._generate_args_docs(parameters),
            'return_type': self._infer_return_type(description),
            'return_description': "The result of the operation",
            'param_docs': self._generate_param_docs(parameters),
            'validation_logic': self._generate_validation_logic(description, language),
            'field_name': name,
            'methods': "",
            'fields': "",
            'endpoint': name.replace('_', '-'),
            'method': "POST" if any(word in desc_lower for word in ['create', 'add', 'update']) else "GET",
            'request_handling': "data = request.get_json()",
            'business_logic': f"# Implement {description}\n        result = None  # TODO: Add implementation"
        })
        
        return info
    
    def _generate_function_body(self, description: str, language: str) -> str:
        """Generate function body based on description"""
        desc_lower = description.lower()
        
        # Email validation
        if "email" in desc_lower and "valid" in desc_lower:
            if language == "python":
                return '''    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email) is not None'''
            elif language == "javascript":
                return '''    const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$/;
    return emailPattern.test(email);'''
            elif language == "java":
                return '''    String emailPattern = "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\\\.[a-zA-Z]{2,}$";
    return email.matches(emailPattern);'''
        
        # Password validation
        if "password" in desc_lower and ("hash" in desc_lower or "encrypt" in desc_lower):
            if language == "python":
                return '''    import hashlib
    import secrets
    salt = secrets.token_hex(16)
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)'''
            elif language == "javascript":
                return '''    const crypto = require('crypto');
    const salt = crypto.randomBytes(16).toString('hex');
    return crypto.pbkdf2Sync(password, salt, 100000, 64, 'sha256').toString('hex');'''
        
        # Default implementation
        if language == "python":
            return "    # TODO: Implement function logic\n    pass"
        elif language == "javascript":
            return "    // TODO: Implement function logic"
        elif language == "java":
            return "    // TODO: Implement method logic\n    return null;"
        
        return "// TODO: Implement logic"
    
    def _generate_validation_logic(self, description: str, language: str) -> str:
        """Generate validation logic"""
        desc_lower = description.lower()
        
        if "email" in desc_lower:
            if language == "python":
                return '''    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, {field_name}):
        return False'''
            else:
                return "// Email validation logic"
        
        return "# Add validation logic here" if language == "python" else "// Add validation logic here"
    
    def _generate_args_docs(self, parameters: str) -> str:
        """Generate argument documentation"""
        if not parameters:
            return ""
        
        params = [p.strip() for p in parameters.split(',') if p.strip()]
        docs = []
        for param in params:
            docs.append(f"        {param}: Description of {param}")
        
        return '\n'.join(docs)
    
    def _generate_param_docs(self, parameters: str) -> str:
        """Generate parameter documentation for JavaScript"""
        if not parameters:
            return ""
        
        params = [p.strip() for p in parameters.split(',') if p.strip()]
        docs = []
        for param in params:
            docs.append(f"     * @param {param} Description of {param}")
        
        return '\n'.join(docs)
    
    def _infer_return_type(self, description: str) -> str:
        """Infer return type from description"""
        desc_lower = description.lower()
        
        if "valid" in desc_lower or "check" in desc_lower:
            return "bool"
        elif "list" in desc_lower or "array" in desc_lower:
            return "list"
        elif "string" in desc_lower or "text" in desc_lower:
            return "str"
        elif "number" in desc_lower or "count" in desc_lower:
            return "int"
        
        return "Any"
    
    def modify_existing_code(self, existing_code: str, description: str, language: str) -> str:
        """Modify existing code based on description"""
        try:
            if language == "python":
                return self._modify_python_code(existing_code, description)
            elif language == "javascript":
                return self._modify_javascript_code(existing_code, description)
            else:
                # For other languages, append the new code
                new_code = self.generate_code(description, language)
                return f"{existing_code}\n\n{new_code}"
        except Exception as e:
            logger.error(f"Error modifying code: {e}")
            return existing_code
    
    def _modify_python_code(self, code: str, description: str) -> str:
        """Modify Python code using AST"""
        try:
            tree = ast.parse(code)
            # Simple modification: add a new function
            new_function = self.generate_code(description, "python", "function")
            return f"{code}\n\n{new_function}"
        except Exception:
            # If AST parsing fails, just append
            new_function = self.generate_code(description, "python", "function")
            return f"{code}\n\n{new_function}"
    
    def _modify_javascript_code(self, code: str, description: str) -> str:
        """Modify JavaScript code"""
        # Simple approach: append new function
        new_function = self.generate_code(description, "javascript", "function")
        return f"{code}\n\n{new_function}"


# Global instance
code_generator = CodeGenerator()


def generate_code_from_description(description: str, language: str = "python", 
                                 code_type: str = "function", context: Dict = None) -> str:
    """Main entry point for code generation"""
    return code_generator.generate_code(description, language, code_type, context)


def modify_code(existing_code: str, description: str, language: str) -> str:
    """Main entry point for code modification"""
    return code_generator.modify_existing_code(existing_code, description, language)
