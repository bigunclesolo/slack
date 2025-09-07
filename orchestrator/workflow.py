"""
Workflow Orchestrator
Coordinates NLP processing, GitHub operations, and Slack responses
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from shared.models import (
    SlackRequest, ProcessedRequest, GitHubOperation, 
    WorkflowExecution, WorkflowStep, OperationStatus
)
from shared.messaging import get_message_queue, get_event_bus
from shared.config import get_settings
from nlp_engine.processor import process_natural_language
from github_engine.client import execute_github_operation

logger = logging.getLogger(__name__)
settings = get_settings()


class WorkflowOrchestrator:
    """Main orchestrator for handling user requests"""
    
    def __init__(self):
        self.message_queue = get_message_queue()
        self.event_bus = get_event_bus()
        self.active_workflows = {}
        
        # Register event handlers
        self.event_bus.register_handler("workflow_step_completed", self.handle_step_completion)
        self.event_bus.register_handler("workflow_step_failed", self.handle_step_failure)
    
    async def start(self):
        """Start the orchestrator and begin processing requests"""
        logger.info("Starting workflow orchestrator...")
        
        # Start consumer tasks for different request types
        consumers = [
            asyncio.create_task(self.process_github_requests()),
            asyncio.create_task(self.process_code_requests()),
            asyncio.create_task(self.process_pr_requests()),
        ]
        
        # Wait for all consumers
        await asyncio.gather(*consumers)
    
    async def process_github_requests(self):
        """Process GitHub operation requests"""
        async for message in self.message_queue.consume("github_requests"):
            try:
                request = SlackRequest(**message)
                await self.handle_request(request)
            except Exception as e:
                logger.error(f"Error processing GitHub request: {e}")
    
    async def process_code_requests(self):
        """Process code generation requests"""
        async for message in self.message_queue.consume("code_requests"):
            try:
                request = SlackRequest(**message)
                await self.handle_request(request, workflow_type="code")
            except Exception as e:
                logger.error(f"Error processing code request: {e}")
    
    async def process_pr_requests(self):
        """Process pull request requests"""
        async for message in self.message_queue.consume("pr_requests"):
            try:
                request = SlackRequest(**message)
                await self.handle_request(request, workflow_type="pr")
            except Exception as e:
                logger.error(f"Error processing PR request: {e}")
    
    async def handle_request(self, request: SlackRequest, workflow_type: str = "github"):
        """Handle incoming user request"""
        execution_id = str(uuid.uuid4())
        
        logger.info(f"Handling {workflow_type} request {execution_id} from user {request.user_id}")
        
        # Create workflow steps based on request type
        steps = self.create_workflow_steps(request, workflow_type)
        
        # Create workflow execution
        workflow = WorkflowExecution(
            execution_id=execution_id,
            request_id=str(uuid.uuid4()),
            user_id=request.user_id,
            channel_id=request.channel_id,
            steps=steps,
            status=OperationStatus.PROCESSING
        )
        
        # Store workflow
        self.active_workflows[execution_id] = workflow
        
        # Start processing
        await self.execute_workflow(workflow)
    
    def create_workflow_steps(self, request: SlackRequest, workflow_type: str) -> List[WorkflowStep]:
        """Create workflow steps based on request type"""
        steps = []
        
        # Step 1: NLP Processing (always first)
        steps.append(WorkflowStep(
            step_id="nlp_processing",
            step_type="nlp",
            parameters={
                "text": request.command,
                "user_id": request.user_id
            }
        ))
        
        if workflow_type == "github":
            # Standard GitHub workflow
            steps.extend([
                WorkflowStep(
                    step_id="validate_permissions",
                    step_type="validation",
                    parameters={"user_id": request.user_id},
                    dependencies=["nlp_processing"]
                ),
                WorkflowStep(
                    step_id="execute_github_operation",
                    step_type="github",
                    parameters={},
                    dependencies=["validate_permissions"]
                ),
                WorkflowStep(
                    step_id="send_result_notification",
                    step_type="notification",
                    parameters={
                        "channel_id": request.channel_id,
                        "user_id": request.user_id
                    },
                    dependencies=["execute_github_operation"]
                )
            ])
        
        elif workflow_type == "code":
            # Code generation workflow
            steps.extend([
                WorkflowStep(
                    step_id="generate_code",
                    step_type="code_generation",
                    parameters={},
                    dependencies=["nlp_processing"]
                ),
                WorkflowStep(
                    step_id="create_file_or_pr",
                    step_type="github",
                    parameters={"auto_create_pr": True},
                    dependencies=["generate_code"]
                ),
                WorkflowStep(
                    step_id="send_code_notification",
                    step_type="notification",
                    parameters={
                        "channel_id": request.channel_id,
                        "user_id": request.user_id,
                        "include_code": True
                    },
                    dependencies=["create_file_or_pr"]
                )
            ])
        
        elif workflow_type == "pr":
            # Pull request workflow
            steps.extend([
                WorkflowStep(
                    step_id="analyze_pr_request",
                    step_type="pr_analysis",
                    parameters={},
                    dependencies=["nlp_processing"]
                ),
                WorkflowStep(
                    step_id="execute_pr_operation",
                    step_type="github",
                    parameters={"operation_focus": "pull_request"},
                    dependencies=["analyze_pr_request"]
                ),
                WorkflowStep(
                    step_id="send_pr_notification",
                    step_type="notification",
                    parameters={
                        "channel_id": request.channel_id,
                        "user_id": request.user_id,
                        "notification_type": "pr_result"
                    },
                    dependencies=["execute_pr_operation"]
                )
            ])
        
        return steps
    
    async def execute_workflow(self, workflow: WorkflowExecution):
        """Execute a workflow step by step"""
        logger.info(f"Starting workflow execution {workflow.execution_id}")
        
        while not workflow.is_completed():
            current_step = workflow.get_current_step()
            if not current_step:
                break
            
            # Check if dependencies are satisfied
            if not self.are_dependencies_satisfied(workflow, current_step):
                logger.warning(f"Dependencies not satisfied for step {current_step.step_id}")
                workflow.errors.append(f"Dependencies not satisfied for step {current_step.step_id}")
                workflow.status = OperationStatus.FAILED
                break
            
            # Execute the step
            try:
                logger.info(f"Executing step {current_step.step_id} in workflow {workflow.execution_id}")
                result = await self.execute_step(workflow, current_step)
                
                # Store result
                workflow.results[current_step.step_id] = result
                
                # Advance to next step
                workflow.advance_step()
                
                # Emit step completion event
                await self.event_bus.emit("workflow_step_completed", {
                    "workflow_id": workflow.execution_id,
                    "step_id": current_step.step_id,
                    "result": result
                })
                
            except Exception as e:
                logger.error(f"Error executing step {current_step.step_id}: {e}")
                
                # Handle retries
                current_step.retry_count += 1
                if current_step.retry_count < current_step.max_retries:
                    logger.info(f"Retrying step {current_step.step_id} (attempt {current_step.retry_count + 1})")
                    await asyncio.sleep(2 ** current_step.retry_count)  # Exponential backoff
                    continue
                
                # Max retries reached
                workflow.errors.append(f"Step {current_step.step_id} failed: {str(e)}")
                workflow.status = OperationStatus.FAILED
                
                await self.event_bus.emit("workflow_step_failed", {
                    "workflow_id": workflow.execution_id,
                    "step_id": current_step.step_id,
                    "error": str(e)
                })
                break
        
        # Mark workflow as completed
        if workflow.is_completed() and workflow.status != OperationStatus.FAILED:
            workflow.status = OperationStatus.COMPLETED
            workflow.end_time = datetime.now()
            
            logger.info(f"Workflow {workflow.execution_id} completed successfully")
            
            await self.event_bus.emit("workflow_completed", {
                "workflow_id": workflow.execution_id,
                "results": workflow.results
            })
        
        # Clean up
        if workflow.execution_id in self.active_workflows:
            del self.active_workflows[workflow.execution_id]
    
    def are_dependencies_satisfied(self, workflow: WorkflowExecution, step: WorkflowStep) -> bool:
        """Check if all dependencies for a step are satisfied"""
        for dep in step.dependencies:
            if dep not in workflow.results:
                return False
        return True
    
    async def execute_step(self, workflow: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute a single workflow step"""
        if step.step_type == "nlp":
            return await self.execute_nlp_step(workflow, step)
        elif step.step_type == "validation":
            return await self.execute_validation_step(workflow, step)
        elif step.step_type == "github":
            return await self.execute_github_step(workflow, step)
        elif step.step_type == "code_generation":
            return await self.execute_code_generation_step(workflow, step)
        elif step.step_type == "pr_analysis":
            return await self.execute_pr_analysis_step(workflow, step)
        elif step.step_type == "notification":
            return await self.execute_notification_step(workflow, step)
        else:
            raise ValueError(f"Unknown step type: {step.step_type}")
    
    async def execute_nlp_step(self, workflow: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute NLP processing step"""
        text = step.parameters["text"]
        
        # Send processing notification
        await self.send_status_update(
            workflow.channel_id,
            workflow.user_id,
            "🧠 Analyzing your request..."
        )
        
        # Process with NLP
        processed = await process_natural_language(text)
        
        return {
            "processed_request": processed.dict(),
            "intent": processed.intent,
            "entities": processed.entities,
            "confidence": processed.confidence
        }
    
    async def execute_validation_step(self, workflow: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute validation step"""
        user_id = step.parameters["user_id"]
        nlp_result = workflow.results.get("nlp_processing", {})
        
        # Basic validation - in production this would check user permissions,
        # repository access, rate limits, etc.
        
        entities = nlp_result.get("entities", {})
        repository = entities.get("repository")
        
        if not repository:
            # Try to infer repository from user preferences or recent activity
            repository = f"user-{user_id}/default-repo"  # Placeholder
        
        return {
            "validated": True,
            "repository": repository,
            "user_permissions": ["read", "write"],  # Placeholder
            "rate_limit_ok": True
        }
    
    async def execute_github_step(self, workflow: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute GitHub operation step"""
        nlp_result = workflow.results.get("nlp_processing", {})
        validation_result = workflow.results.get("validate_permissions", {})
        
        # Send processing notification
        await self.send_status_update(
            workflow.channel_id,
            workflow.user_id,
            "⚙️ Executing GitHub operation..."
        )
        
        # Create GitHub operation from NLP result
        processed_request = ProcessedRequest(**nlp_result["processed_request"])
        operation = GitHubOperation.from_processed_request(processed_request, workflow.user_id)
        
        # Set repository if validated
        if validation_result and validation_result.get("repository"):
            operation.repository = validation_result["repository"]
        
        # Execute the operation
        result = await execute_github_operation(operation)
        
        return result
    
    async def execute_code_generation_step(self, workflow: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute code generation step"""
        nlp_result = workflow.results.get("nlp_processing", {})
        
        await self.send_status_update(
            workflow.channel_id,
            workflow.user_id,
            "💻 Generating code..."
        )
        
        # This would integrate with code generation service
        # For now, return a placeholder
        return {
            "generated_code": "# Generated code placeholder",
            "language": "python",
            "file_suggestion": "generated_code.py"
        }
    
    async def execute_pr_analysis_step(self, workflow: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute PR analysis step"""
        nlp_result = workflow.results.get("nlp_processing", {})
        
        # Analyze the PR request for specific operations
        return {
            "pr_action": "create",  # create, merge, close, review
            "target_branch": "main",
            "source_branch": "feature-branch"
        }
    
    async def execute_notification_step(self, workflow: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Execute notification step"""
        channel_id = step.parameters["channel_id"]
        user_id = step.parameters["user_id"]
        
        # Gather results from previous steps
        results = workflow.results
        
        # Create summary message
        if "execute_github_operation" in results:
            github_result = results["execute_github_operation"]
            if github_result.get("success"):
                message = "✅ GitHub operation completed successfully!"
                if github_result.get("pr_url"):
                    message += f"\n🔗 Pull Request: {github_result['pr_url']}"
            else:
                message = f"❌ GitHub operation failed: {github_result.get('error', 'Unknown error')}"
        else:
            message = "✅ Request processed successfully!"
        
        await self.send_final_notification(channel_id, user_id, message, results)
        
        return {"notification_sent": True}
    
    async def send_status_update(self, channel_id: str, user_id: str, status: str):
        """Send a status update to Slack"""
        await self.message_queue.publish("operation_updates", {
            "channel_id": channel_id,
            "user_id": user_id,
            "status": status,
            "timestamp": datetime.now().isoformat()
        })
    
    async def send_final_notification(self, channel_id: str, user_id: str, 
                                    message: str, results: Dict[str, Any]):
        """Send final notification with results"""
        notification_data = {
            "channel_id": channel_id,
            "user_id": user_id,
            "message": message,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.message_queue.publish("final_notifications", notification_data)
    
    async def handle_step_completion(self, data: Dict[str, Any]):
        """Handle workflow step completion event"""
        workflow_id = data["workflow_id"]
        step_id = data["step_id"]
        
        logger.info(f"Step {step_id} completed in workflow {workflow_id}")
    
    async def handle_step_failure(self, data: Dict[str, Any]):
        """Handle workflow step failure event"""
        workflow_id = data["workflow_id"]
        step_id = data["step_id"]
        error = data["error"]
        
        logger.error(f"Step {step_id} failed in workflow {workflow_id}: {error}")
    
    async def get_workflow_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a workflow"""
        if execution_id in self.active_workflows:
            workflow = self.active_workflows[execution_id]
            return {
                "execution_id": execution_id,
                "status": workflow.status.value,
                "current_step": workflow.current_step,
                "total_steps": len(workflow.steps),
                "results": workflow.results,
                "errors": workflow.errors
            }
        return None


# Global orchestrator instance
orchestrator = WorkflowOrchestrator()


async def start_orchestrator():
    """Start the workflow orchestrator"""
    await orchestrator.start()


if __name__ == "__main__":
    asyncio.run(start_orchestrator())
