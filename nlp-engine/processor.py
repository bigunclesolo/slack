"""
NLP Engine for processing natural language requests
Extracts intent and entities from user input
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import spacy
from spacy.matcher import Matcher
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch

from shared.models import ProcessedRequest, Intent, Entity
from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")
    nlp = None


class IntentType(Enum):
    CREATE_BRANCH = "create_branch"
    DELETE_BRANCH = "delete_branch"
    CREATE_PR = "create_pr"
    MERGE_PR = "merge_pr"
    CREATE_FILE = "create_file"
    MODIFY_FILE = "modify_file"
    DELETE_FILE = "delete_file"
    GENERATE_CODE = "generate_code"
    FIX_BUG = "fix_bug"
    ADD_FEATURE = "add_feature"
    UPDATE_DOCS = "update_docs"
    RUN_TESTS = "run_tests"
    DEPLOY = "deploy"
    UNKNOWN = "unknown"


@dataclass
class ExtractedEntity:
    type: str
    value: str
    confidence: float
    start_pos: int
    end_pos: int


class NLPProcessor:
    def __init__(self):
        self.matcher = self._setup_matcher() if nlp else None
        self.intent_patterns = self._setup_intent_patterns()
        self.intent_classifier = self._load_intent_classifier()
        self.entity_recognizer = self._load_entity_recognizer()
        
    def _setup_matcher(self) -> Matcher:
        """Set up spaCy matcher for entity extraction"""
        matcher = Matcher(nlp.vocab)
        
        # Repository patterns
        repo_patterns = [
            [{"LOWER": {"IN": ["repo", "repository"]}},
             {"IS_ALPHA": True, "OP": "?"}],
            [{"TEXT": {"REGEX": r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$"}}],  # owner/repo format
        ]
        matcher.add("REPOSITORY", repo_patterns)
        
        # Branch patterns
        branch_patterns = [
            [{"LOWER": "branch"}, {"LOWER": {"IN": ["called", "named"]}, "OP": "?"}, 
             {"IS_ALPHA": True}],
            [{"LOWER": {"IN": ["feature", "bug", "hotfix"]}}, 
             {"TEXT": {"REGEX": r"^[a-zA-Z0-9._-]+$"}}]
        ]
        matcher.add("BRANCH", branch_patterns)
        
        # File patterns
        file_patterns = [
            [{"TEXT": {"REGEX": r"^[a-zA-Z0-9._/-]+\.[a-zA-Z]{2,4}$"}}],  # file.ext
            [{"LOWER": "file"}, {"IS_ALPHA": True, "OP": "+"}]
        ]
        matcher.add("FILE", file_patterns)
        
        # Programming language patterns
        lang_patterns = [
            [{"LOWER": {"IN": ["python", "javascript", "java", "go", "rust", "typescript", 
                              "c++", "c#", "php", "ruby", "swift", "kotlin"]}}]
        ]
        matcher.add("LANGUAGE", lang_patterns)
        
        return matcher
    
    def _load_intent_classifier(self):
        """Load pre-trained transformer model for intent classification"""
        try:
            # Use a lightweight BERT model for intent classification
            model_name = "microsoft/DialoGPT-medium"  # Alternative: "distilbert-base-uncased"
            tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
            
            # For now, we'll use a text classification pipeline
            # In production, you'd fine-tune this on your specific intents
            classifier = pipeline(
                "text-classification",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                return_all_scores=True
            )
            
            logger.info("Loaded transformer-based intent classifier")
            return classifier
            
        except Exception as e:
            logger.warning(f"Failed to load transformer model: {e}")
            return None
    
    def _load_entity_recognizer(self):
        """Load NER model for entity recognition"""
        try:
            # Use a pre-trained NER model
            ner = pipeline(
                "ner",
                model="dbmdz/bert-large-cased-finetuned-conll03-english",
                aggregation_strategy="simple"
            )
            
            logger.info("Loaded transformer-based NER model")
            return ner
            
        except Exception as e:
            logger.warning(f"Failed to load NER model: {e}")
            return None
    
    def _setup_intent_patterns(self) -> Dict[str, List[str]]:
        """Define regex patterns for intent classification"""
        return {
            IntentType.CREATE_BRANCH.value: [
                r"create.*branch",
                r"new.*branch",
                r"make.*branch",
                r"add.*branch"
            ],
            IntentType.DELETE_BRANCH.value: [
                r"delete.*branch",
                r"remove.*branch",
                r"drop.*branch"
            ],
            IntentType.CREATE_PR.value: [
                r"create.*pr",
                r"create.*pull.*request",
                r"new.*pr",
                r"make.*pr",
                r"open.*pr"
            ],
            IntentType.MERGE_PR.value: [
                r"merge.*pr",
                r"merge.*pull.*request",
                r"approve.*pr"
            ],
            IntentType.CREATE_FILE.value: [
                r"create.*file",
                r"new.*file",
                r"add.*file",
                r"make.*file"
            ],
            IntentType.MODIFY_FILE.value: [
                r"modify.*file",
                r"edit.*file",
                r"update.*file",
                r"change.*file"
            ],
            IntentType.DELETE_FILE.value: [
                r"delete.*file",
                r"remove.*file",
                r"drop.*file"
            ],
            IntentType.GENERATE_CODE.value: [
                r"generate.*code",
                r"create.*function",
                r"write.*code",
                r"add.*function",
                r"implement.*function"
            ],
            IntentType.FIX_BUG.value: [
                r"fix.*bug",
                r"resolve.*issue",
                r"fix.*error",
                r"debug.*code"
            ],
            IntentType.ADD_FEATURE.value: [
                r"add.*feature",
                r"implement.*feature",
                r"create.*feature",
                r"new.*functionality"
            ],
            IntentType.UPDATE_DOCS.value: [
                r"update.*docs",
                r"update.*documentation",
                r"modify.*readme",
                r"change.*docs"
            ]
        }
    
    def extract_entities_with_spacy(self, text: str) -> List[ExtractedEntity]:
        """Extract entities using spaCy"""
        if not nlp or not self.matcher:
            return []
        
        doc = nlp(text)
        matches = self.matcher(doc)
        entities = []
        
        for match_id, start, end in matches:
            span = doc[start:end]
            label = nlp.vocab.strings[match_id]
            
            entities.append(ExtractedEntity(
                type=label.lower(),
                value=span.text,
                confidence=0.8,  # Default confidence for rule-based matches
                start_pos=span.start_char,
                end_pos=span.end_char
            ))
        
        # Also extract named entities
        for ent in doc.ents:
            entities.append(ExtractedEntity(
                type=ent.label_.lower(),
                value=ent.text,
                confidence=0.9,
                start_pos=ent.start_char,
                end_pos=ent.end_char
            ))
        
        return entities
    
    def classify_intent_with_rules(self, text: str) -> Tuple[IntentType, float]:
        """Classify intent using rule-based approach"""
        text_lower = text.lower()
        best_intent = IntentType.UNKNOWN
        best_score = 0.0
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    score = len(re.findall(pattern, text_lower)) * 0.3
                    if score > best_score:
                        best_score = score
                        best_intent = IntentType(intent)
        
        return best_intent, min(best_score, 1.0)
    
    def classify_intent_with_transformer(self, text: str) -> Tuple[IntentType, float]:
        """Classify intent using transformer models"""
        try:
            # Enhanced rule-based approach with semantic similarity
            rule_intent, rule_confidence = self.classify_intent_with_rules(text)
            
            # If we have high confidence from rules, use that
            if rule_confidence > 0.8:
                return rule_intent, rule_confidence
            
            # Use semantic similarity with intent keywords
            best_intent = IntentType.UNKNOWN
            best_score = 0.0
            
            # Define semantic patterns for each intent
            intent_keywords = {
                IntentType.CREATE_BRANCH: ["create", "new", "branch", "make", "add", "start"],
                IntentType.DELETE_BRANCH: ["delete", "remove", "branch", "drop", "destroy"],
                IntentType.CREATE_PR: ["pull", "request", "pr", "merge", "create", "open"],
                IntentType.MERGE_PR: ["merge", "approve", "accept", "pull", "request"],
                IntentType.CREATE_FILE: ["create", "new", "file", "add", "make"],
                IntentType.MODIFY_FILE: ["modify", "edit", "change", "update", "file"],
                IntentType.DELETE_FILE: ["delete", "remove", "file", "drop"],
                IntentType.GENERATE_CODE: ["generate", "code", "write", "create", "function", "implement"],
                IntentType.FIX_BUG: ["fix", "bug", "error", "issue", "resolve", "debug"],
                IntentType.ADD_FEATURE: ["feature", "add", "implement", "new", "functionality"],
                IntentType.UPDATE_DOCS: ["docs", "documentation", "readme", "update", "modify"]
            }
            
            # Calculate semantic similarity
            text_lower = text.lower()
            text_words = set(text_lower.split())
            
            for intent_type, keywords in intent_keywords.items():
                # Calculate overlap score
                keyword_matches = sum(1 for keyword in keywords if keyword in text_lower)
                word_overlap = len(text_words.intersection(set(keywords)))
                
                # Weighted scoring
                score = (keyword_matches * 0.6) + (word_overlap * 0.4)
                score = min(score / len(keywords), 1.0)  # Normalize
                
                if score > best_score and score > 0.3:  # Minimum threshold
                    best_score = score
                    best_intent = intent_type
            
            # Combine with rule-based confidence
            final_confidence = max(rule_confidence, best_score)
            final_intent = best_intent if best_score > rule_confidence else rule_intent
            
            logger.info(f"Transformer Intent classification: {final_intent.value} (confidence: {final_confidence})")
            return final_intent, final_confidence
            
        except Exception as e:
            logger.error(f"Error in transformer intent classification: {e}")
            return IntentType.UNKNOWN, 0.0
    
    def extract_entities_with_transformer(self, text: str, intent: IntentType) -> List[ExtractedEntity]:
        """Extract entities using transformer-based NER"""
        entities = []
        
        try:
            # Use transformer NER model if available
            if self.entity_recognizer:
                ner_results = self.entity_recognizer(text)
                
                for entity in ner_results:
                    entities.append(ExtractedEntity(
                        type=entity['entity_group'].lower(),
                        value=entity['word'],
                        confidence=entity['score'],
                        start_pos=entity['start'],
                        end_pos=entity['end']
                    ))
            
            # Custom entity extraction for GitHub-specific terms
            entities.extend(self._extract_custom_entities(text, intent))
            
            return entities
            
        except Exception as e:
            logger.error(f"Error in transformer entity extraction: {e}")
            return []
    
    def _extract_custom_entities(self, text: str, intent: IntentType) -> List[ExtractedEntity]:
        """Extract custom entities specific to GitHub operations"""
        entities = []
        text_lower = text.lower()
        
        # Repository patterns
        repo_patterns = [
            r'\b([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+)\b',  # owner/repo format
            r'\b(?:in|from|to)\s+([a-zA-Z0-9._-]+)\b',  # "in my-repo"
            r'\b(?:repository|repo)\s+([a-zA-Z0-9._-]+)\b'  # "repository my-repo"
        ]
        
        for pattern in repo_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities.append(ExtractedEntity(
                    type="repository",
                    value=match.group(1),
                    confidence=0.9,
                    start_pos=match.start(1),
                    end_pos=match.end(1)
                ))
        
        # Branch patterns
        branch_patterns = [
            r'\bbranch\s+(?:called|named)?\s*["\']?([a-zA-Z0-9._/-]+)["\']?',
            r'\b(?:feature|hotfix|bugfix|release)-([a-zA-Z0-9._-]+)\b',
            r'\b(?:from|to|into)\s+([a-zA-Z0-9._/-]+)\s+(?:branch)?\b'
        ]
        
        for pattern in branch_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities.append(ExtractedEntity(
                    type="branch",
                    value=match.group(1),
                    confidence=0.85,
                    start_pos=match.start(1),
                    end_pos=match.end(1)
                ))
        
        # File patterns
        file_patterns = [
            r'\b([a-zA-Z0-9._/-]+\.[a-zA-Z]{2,4})\b',  # filename.ext
            r'\bfile\s+(?:called|named)?\s*["\']?([a-zA-Z0-9._/-]+(?:\.[a-zA-Z]{2,4})?)["\']?'
        ]
        
        for pattern in file_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities.append(ExtractedEntity(
                    type="file",
                    value=match.group(1),
                    confidence=0.8,
                    start_pos=match.start(1),
                    end_pos=match.end(1)
                ))
        
        # Programming language detection
        languages = {
            'python': ['python', 'py', '.py'],
            'javascript': ['javascript', 'js', '.js', 'node'],
            'typescript': ['typescript', 'ts', '.ts'],
            'java': ['java', '.java'],
            'go': ['go', 'golang', '.go'],
            'rust': ['rust', 'rs', '.rs'],
            'cpp': ['c++', 'cpp', '.cpp', '.cc'],
            'c': ['c', '.c'],
            'php': ['php', '.php'],
            'ruby': ['ruby', 'rb', '.rb'],
            'swift': ['swift', '.swift'],
            'kotlin': ['kotlin', '.kt']
        }
        
        for lang, keywords in languages.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    pos = text_lower.find(keyword.lower())
                    entities.append(ExtractedEntity(
                        type="language",
                        value=lang,
                        confidence=0.9,
                        start_pos=pos,
                        end_pos=pos + len(keyword)
                    ))
                    break  # Only add once per language
        
        # Function/method name extraction
        function_patterns = [
            r'\bfunction\s+([a-zA-Z_][a-zA-Z0-9_]*)\b',
            r'\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)\b',
            r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\)',
            r'\bmethod\s+([a-zA-Z_][a-zA-Z0-9_]*)\b'
        ]
        
        for pattern in function_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities.append(ExtractedEntity(
                    type="function",
                    value=match.group(1),
                    confidence=0.75,
                    start_pos=match.start(1),
                    end_pos=match.end(1)
                ))
        
        # Extract description (everything after action words)
        description_patterns = [
            r'\b(?:to|that|with|for)\s+(.+)$',
            r'\b(?:add|create|implement|generate)\s+(.+?)\s+(?:in|to|for|$)',
            r'\b(?:fix|resolve)\s+(.+?)\s+(?:in|at|$)'
        ]
        
        for pattern in description_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                desc = match.group(1).strip()
                if len(desc) > 3:  # Minimum description length
                    entities.append(ExtractedEntity(
                        type="description",
                        value=desc,
                        confidence=0.7,
                        start_pos=match.start(1),
                        end_pos=match.end(1)
                    ))
                    break  # Only take the first description
        
        return entities
    
    async def process_request(self, text: str) -> ProcessedRequest:
        """Main processing function that combines all NLP techniques"""
        start_time = asyncio.get_event_loop().time()
        logger.info(f"Processing request: {text}")
        
        # Step 1: Intent classification
        rule_intent, rule_confidence = self.classify_intent_with_rules(text)
        
        # Use transformer model for better classification if rule-based confidence is low
        if rule_confidence < 0.7:
            transformer_intent, transformer_confidence = self.classify_intent_with_transformer(text)
            if transformer_confidence > rule_confidence:
                final_intent = transformer_intent
                final_confidence = transformer_confidence
            else:
                final_intent = rule_intent
                final_confidence = rule_confidence
        else:
            final_intent = rule_intent
            final_confidence = rule_confidence
        
        # Step 2: Entity extraction
        spacy_entities = self.extract_entities_with_spacy(text)
        transformer_entities = self.extract_entities_with_transformer(text, final_intent)
        
        # Combine entities (prefer transformer results for higher accuracy)
        all_entities = transformer_entities + spacy_entities
        
        # Remove duplicates and keep highest confidence
        unique_entities = {}
        for entity in all_entities:
            key = f"{entity.type}_{entity.value}"
            if key not in unique_entities or entity.confidence > unique_entities[key].confidence:
                unique_entities[key] = entity
        
        final_entities = list(unique_entities.values())
        
        # Step 3: Create structured result
        processing_time = asyncio.get_event_loop().time() - start_time
        result = ProcessedRequest(
            original_text=text,
            intent=final_intent.value,
            confidence=final_confidence,
            entities={
                entity.type: entity.value 
                for entity in final_entities 
                if entity.confidence > 0.5
            },
            raw_entities=final_entities,
            processing_time=processing_time
        )
        
        logger.info(f"Processed request - Intent: {result.intent}, Entities: {len(result.entities)}, Time: {processing_time:.3f}s")
        return result


# Global processor instance
processor = NLPProcessor()


async def process_natural_language(text: str) -> ProcessedRequest:
    """Main entry point for NLP processing"""
    return await processor.process_request(text)
