"""
GitHub Integration Engine
Handles all GitHub API operations and repository management
"""

import os
import logging
import tempfile
import shutil
from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio

import git
from github import Github, GithubException
from github.Repository import Repository
from github.PullRequest import PullRequest
from github.ContentFile import ContentFile

from shared.models import GitHubOperation, ProcessedRequest
from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GitHubClient:
    def __init__(self, access_token: str = None):
        self.access_token = access_token or settings.github_token
        self.github = Github(self.access_token)
        self.user = self.github.get_user()
        
    def get_repository(self, repo_name: str) -> Repository:
        """Get a GitHub repository object"""
        try:
            # Handle different repository name formats
            if '/' not in repo_name:
                # Assume it's a repo owned by the authenticated user
                repo_name = f"{self.user.login}/{repo_name}"
            
            return self.github.get_repo(repo_name)
        except GithubException as e:
            logger.error(f"Error accessing repository {repo_name}: {e}")
            raise
    
    async def create_branch(self, repo_name: str, branch_name: str, 
                          source_branch: str = "main") -> Dict[str, Any]:
        """Create a new branch in the repository"""
        try:
            repo = self.get_repository(repo_name)
            
            # Get the source branch reference
            try:
                source_ref = repo.get_git_ref(f"heads/{source_branch}")
            except GithubException:
                # Try 'master' if 'main' doesn't exist
                source_ref = repo.get_git_ref("heads/master")
            
            # Create new branch
            new_ref = repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=source_ref.object.sha
            )
            
            logger.info(f"Created branch '{branch_name}' in {repo_name}")
            return {
                "success": True,
                "branch_name": branch_name,
                "ref": new_ref.ref,
                "sha": new_ref.object.sha
            }
            
        except GithubException as e:
            logger.error(f"Error creating branch: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_branch(self, repo_name: str, branch_name: str) -> Dict[str, Any]:
        """Delete a branch from the repository"""
        try:
            repo = self.get_repository(repo_name)
            ref = repo.get_git_ref(f"heads/{branch_name}")
            ref.delete()
            
            logger.info(f"Deleted branch '{branch_name}' from {repo_name}")
            return {
                "success": True,
                "branch_name": branch_name
            }
            
        except GithubException as e:
            logger.error(f"Error deleting branch: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_file(self, repo_name: str, file_path: str, content: str,
                         commit_message: str, branch: str = "main") -> Dict[str, Any]:
        """Create a new file in the repository"""
        try:
            repo = self.get_repository(repo_name)
            
            result = repo.create_file(
                path=file_path,
                message=commit_message,
                content=content,
                branch=branch
            )
            
            logger.info(f"Created file '{file_path}' in {repo_name}")
            return {
                "success": True,
                "file_path": file_path,
                "commit_sha": result["commit"].sha,
                "content_sha": result["content"].sha
            }
            
        except GithubException as e:
            logger.error(f"Error creating file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_file(self, repo_name: str, file_path: str, content: str,
                         commit_message: str, branch: str = "main") -> Dict[str, Any]:
        """Update an existing file in the repository"""
        try:
            repo = self.get_repository(repo_name)
            
            # Get the current file to obtain its SHA
            try:
                file_content = repo.get_contents(file_path, ref=branch)
                current_sha = file_content.sha
            except GithubException:
                # File doesn't exist, create it instead
                return await self.create_file(repo_name, file_path, content, commit_message, branch)
            
            result = repo.update_file(
                path=file_path,
                message=commit_message,
                content=content,
                sha=current_sha,
                branch=branch
            )
            
            logger.info(f"Updated file '{file_path}' in {repo_name}")
            return {
                "success": True,
                "file_path": file_path,
                "commit_sha": result["commit"].sha,
                "content_sha": result["content"].sha
            }
            
        except GithubException as e:
            logger.error(f"Error updating file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_file(self, repo_name: str, file_path: str,
                         commit_message: str, branch: str = "main") -> Dict[str, Any]:
        """Delete a file from the repository"""
        try:
            repo = self.get_repository(repo_name)
            
            # Get the current file to obtain its SHA
            file_content = repo.get_contents(file_path, ref=branch)
            
            result = repo.delete_file(
                path=file_path,
                message=commit_message,
                sha=file_content.sha,
                branch=branch
            )
            
            logger.info(f"Deleted file '{file_path}' from {repo_name}")
            return {
                "success": True,
                "file_path": file_path,
                "commit_sha": result["commit"].sha
            }
            
        except GithubException as e:
            logger.error(f"Error deleting file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_pull_request(self, repo_name: str, title: str, body: str,
                                head_branch: str, base_branch: str = "main") -> Dict[str, Any]:
        """Create a pull request"""
        try:
            repo = self.get_repository(repo_name)
            
            pr = repo.create_pull(
                title=title,
                body=body,
                head=head_branch,
                base=base_branch
            )
            
            logger.info(f"Created PR #{pr.number} in {repo_name}")
            return {
                "success": True,
                "pr_number": pr.number,
                "pr_url": pr.html_url,
                "title": pr.title,
                "body": pr.body
            }
            
        except GithubException as e:
            logger.error(f"Error creating PR: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def merge_pull_request(self, repo_name: str, pr_number: int,
                               commit_title: str = None, merge_method: str = "merge") -> Dict[str, Any]:
        """Merge a pull request"""
        try:
            repo = self.get_repository(repo_name)
            pr = repo.get_pull(pr_number)
            
            if not pr.mergeable:
                return {
                    "success": False,
                    "error": "Pull request is not mergeable"
                }
            
            result = pr.merge(
                commit_title=commit_title or f"Merge pull request #{pr_number}",
                merge_method=merge_method
            )
            
            logger.info(f"Merged PR #{pr_number} in {repo_name}")
            return {
                "success": True,
                "pr_number": pr_number,
                "merged": result.merged,
                "sha": result.sha
            }
            
        except GithubException as e:
            logger.error(f"Error merging PR: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_file_content(self, repo_name: str, file_path: str,
                              branch: str = "main") -> Dict[str, Any]:
        """Get the content of a file from the repository"""
        try:
            repo = self.get_repository(repo_name)
            file_content = repo.get_contents(file_path, ref=branch)
            
            return {
                "success": True,
                "content": file_content.decoded_content.decode('utf-8'),
                "sha": file_content.sha,
                "size": file_content.size
            }
            
        except GithubException as e:
            logger.error(f"Error getting file content: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def list_repository_files(self, repo_name: str, path: str = "",
                                   branch: str = "main") -> List[str]:
        """List files in a repository directory"""
        try:
            repo = self.get_repository(repo_name)
            contents = repo.get_contents(path, ref=branch)
            
            file_list = []
            for content in contents:
                if content.type == "file":
                    file_list.append(content.path)
                elif content.type == "dir":
                    # Recursively list subdirectory files
                    subfiles = await self.list_repository_files(repo_name, content.path, branch)
                    file_list.extend(subfiles)
            
            return file_list
            
        except GithubException as e:
            logger.error(f"Error listing files: {e}")
            return []
    
    async def clone_repository(self, repo_name: str, target_dir: str = None,
                              branch: str = "main") -> str:
        """Clone a repository to local filesystem"""
        if target_dir is None:
            target_dir = tempfile.mkdtemp()
        
        try:
            repo = self.get_repository(repo_name)
            clone_url = f"https://{self.access_token}@github.com/{repo_name}.git"
            
            # Clone the repository
            git_repo = git.Repo.clone_from(
                clone_url,
                target_dir,
                branch=branch,
                depth=1  # Shallow clone for efficiency
            )
            
            logger.info(f"Cloned repository {repo_name} to {target_dir}")
            return target_dir
            
        except Exception as e:
            logger.error(f"Error cloning repository: {e}")
            # Clean up on error
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            raise


class CodeGeneratorWrapper:
    """Wrapper for the enhanced code generator"""
    
    def __init__(self, github_client: GitHubClient):
        self.github_client = github_client
        # Import the enhanced code generator
        try:
            from nlp_engine.code_generator import generate_code_from_description, modify_code
            self.generate_code_func = generate_code_from_description
            self.modify_code_func = modify_code
        except ImportError:
            logger.warning("Enhanced code generator not available, using basic templates")
            self.generate_code_func = None
            self.modify_code_func = None
    
    async def generate_code_from_description(self, description: str, 
                                           language: str = "python", 
                                           code_type: str = "function") -> str:
        """Generate code based on natural language description"""
        if self.generate_code_func:
            return self.generate_code_func(description, language, code_type)
        
        # Fallback to basic template
        return self._basic_template_generation(description, language, code_type)
    
    def _basic_template_generation(self, description: str, language: str, code_type: str) -> str:
        """Basic template generation as fallback"""
        if language == "python":
            if code_type == "class":
                return f'''class GeneratedClass:
    """
    {description}
    """
    
    def __init__(self):
        pass
'''
            else:
                return f'''def generated_function():
    """
    {description}
    """
    # TODO: Implement function logic
    pass
'''
        elif language == "javascript":
            if code_type == "class":
                return f'''class GeneratedClass {{
    /**
     * {description}
     */
    constructor() {{
        // TODO: Initialize class
    }}
}}
'''
            else:
                return f'''function generatedFunction() {{
    /**
     * {description}
     */
    // TODO: Implement function logic
}}
'''
        else:
            return f"// {description}\n// TODO: Implement in {language}"
    
    async def apply_code_changes(self, repo_name: str, file_path: str,
                               original_code: str, new_code: str,
                               branch: str = "main") -> Dict[str, Any]:
        """Apply code changes to a file"""
        commit_message = f"Update {file_path} - automated code changes"
        
        return await self.github_client.update_file(
            repo_name=repo_name,
            file_path=file_path,
            content=new_code,
            commit_message=commit_message,
            branch=branch
        )


# Global client instance
github_client = GitHubClient()
code_generator = CodeGeneratorWrapper(github_client)


async def execute_github_operation(operation: GitHubOperation) -> Dict[str, Any]:
    """Main entry point for executing GitHub operations"""
    
    operation_handlers = {
        "create_branch": github_client.create_branch,
        "delete_branch": github_client.delete_branch,
        "create_file": github_client.create_file,
        "update_file": github_client.update_file,
        "delete_file": github_client.delete_file,
        "create_pr": github_client.create_pull_request,
        "merge_pr": github_client.merge_pull_request,
    }
    
    handler = operation_handlers.get(operation.operation_type)
    if not handler:
        return {
            "success": False,
            "error": f"Unknown operation type: {operation.operation_type}"
        }
    
    try:
        return await handler(**operation.parameters)
    except Exception as e:
        logger.error(f"Error executing operation {operation.operation_type}: {e}")
        return {
            "success": False,
            "error": str(e)
        }
